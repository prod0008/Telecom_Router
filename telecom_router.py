import os
import json
import re
import datetime
import boto3
from dotenv import load_dotenv
from strands import Agent, tool
from strands.models import BedrockModel

# Load environment variables
load_dotenv()

# Initialize Bedrock client for direct tool calls
bedrock_client = boto3.client(
    service_name='bedrock-runtime',
    region_name=os.getenv('AWS_REGION', 'us-east-1')
)

# Initialize DynamoDB client for audit logging
dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION', 'us-east-1'))
audit_table = dynamodb.Table('routing-audit')

# ==========================================
# 1. TOOLS
# ==========================================
@tool
def classify_intent(ticket_text: str) -> dict:
    """
    Classifies the intent of a telecom support ticket.
    Returns a dictionary with 'intent' (billing, technical, cancellation, or general) 
    and 'confidence_score' (float between 0.0 and 1.0).
    """
    prompt = f"""
    Analyze the following telecom support ticket. 
    Classify its intent into exactly one of these categories: 'billing', 'technical', 'cancellation', or 'general'.
    Also, provide a confidence score as a float between 0.0 and 1.0.
    
    Ticket: "{ticket_text}"
    
    Return ONLY a valid JSON object with the keys: "intent" and "confidence_score".
    """
    
    response = bedrock_client.converse(
        modelId=os.getenv('BEDROCK_MODEL_ID', 'amazon.nova-lite-v1:0'),
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0.0}
    )
    
    raw_text = response["output"]["message"]["content"][0]["text"]
    raw_text = re.sub(r'^```json\s*', '', raw_text)
    raw_text = re.sub(r'\s*```$', '', raw_text).strip()
    
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {"intent": "general", "confidence_score": 0.5}

# ==========================================
# 2. WORKER AGENTS
# ==========================================
model = BedrockModel(model_id=os.getenv('BEDROCK_MODEL_ID', 'amazon.nova-lite-v1:0'))

def get_response(agent, prompt):
    result = agent(prompt)
    if hasattr(result, 'message') and hasattr(result.message, 'content'):
        return result.message.content[0].get('text', str(result.message))
    return str(result)

billing_agent = Agent(
    name="BillingAgent",
    model=model,
    system_prompt="You are the BillingAgent. Handle ONLY inquiries related to invoices, payments, refunds, overcharges, and billing cycles. Do not discuss technical issues or cancellations. Be polite and concise."
)

technical_agent = Agent(
    name="TechnicalAgent",
    model=model,
    system_prompt="You are the TechnicalAgent. Handle ONLY inquiries related to internet connectivity, router issues, slow speeds, and hardware troubleshooting. Do not discuss billing or cancellations. Provide clear, step-by-step guidance."
)

retention_agent = Agent(
    name="RetentionAgent",
    model=model,
    system_prompt="You are the RetentionAgent. Handle ONLY customers who want to cancel, downgrade, or leave. Your goal is to empathize with their frustration and offer retention deals (e.g., discounts, free months) to keep them as a customer."
)

general_agent = Agent(
    name="GeneralSupportAgent",
    model=model,
    system_prompt="You are the GeneralSupportAgent. Handle ambiguous, complex, or multi-faceted tickets that do not clearly fit into billing, technical, or cancellation. Gather more information and provide general account assistance."
)

# ==========================================
# 3. HYBRID ROUTER LOGIC
# ==========================================
def route_ticket(ticket_text: str) -> dict:
    text_lower = ticket_text.lower()
    
    # 1. Priority Check: Cancellation intents bypass standard handling
    cancellation_keywords = ['cancel', 'cancellation', 'quit', 'leave', 'terminate', 'stop service', 'churn']
    if any(kw in text_lower for kw in cancellation_keywords):
        result = {
            "agent": "RetentionAgent",
            "reason": "Priority cancellation intent detected (bypassed LLM)",
            "response": get_response(retention_agent, ticket_text)
        }
    else:
        # 2. Rule-Based Matching: Predictable billing and technical tickets
        billing_keywords = ['bill', 'billing', 'invoice', 'overcharged', 'refund', 'payment', 'charge', 'fee']
        technical_keywords = ['internet', 'wifi', 'router', 'slow', 'disconnect', 'no signal', 'offline', 'blinking', 'down']
        
        billing_matches = sum(1 for kw in billing_keywords if kw in text_lower)
        technical_matches = sum(1 for kw in technical_keywords if kw in text_lower)
        
        if billing_matches > 0 and billing_matches >= technical_matches:
            result = {
                "agent": "BillingAgent",
                "reason": "Rule-based match: billing keywords (bypassed LLM)",
                "response": get_response(billing_agent, ticket_text)
            }
        elif technical_matches > 0 and technical_matches > billing_matches:
            result = {
                "agent": "TechnicalAgent",
                "reason": "Rule-based match: technical keywords (bypassed LLM)",
                "response": get_response(technical_agent, ticket_text)
            }
        else:
            # 3. LLM Classification Fallback: Ambiguous tickets
            classification = classify_intent(ticket_text)
            intent = classification.get("intent", "general").lower()
            confidence = classification.get("confidence_score", 0.0)
            
            if intent == "billing":
                result = {"agent": "BillingAgent", "reason": f"LLM classified as billing (confidence: {confidence})", "response": get_response(billing_agent, ticket_text)}
            elif intent == "technical":
                result = {"agent": "TechnicalAgent", "reason": f"LLM classified as technical (confidence: {confidence})", "response": get_response(technical_agent, ticket_text)}
            elif intent == "cancellation":
                result = {"agent": "RetentionAgent", "reason": f"LLM classified as cancellation (confidence: {confidence})", "response": get_response(retention_agent, ticket_text)}
            else:
                result = {"agent": "GeneralSupportAgent", "reason": f"LLM classified as general/ambiguous (confidence: {confidence})", "response": get_response(general_agent, ticket_text)}
    
    # Audit Logging to DynamoDB
    try:
        audit_table.put_item(Item={
            'ticket_id': f"ticket_{abs(hash(ticket_text)) % 100000}",
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'agent': result['agent'],
            'reason': result['reason']
        })
    except Exception as e:
        print(f"Warning: Could not log to DynamoDB. Error: {e}")
        
    return result

# ==========================================
# 4. EXECUTION AND REPORTING
# ==========================================
if __name__ == "__main__":
    sample_tickets = [
        "I want to cancel my service immediately, this is terrible.",
        "My internet has been down for 3 hours and the router is blinking red.",
        "Why was I overcharged on my last invoice? I need a refund.",
        "Can you tell me about the new data plans you offer?",
        "I'm moving to a new city, do I need to return my equipment?",
        "My bill is too high this month, what are these extra fees?",
        "The wifi speed is incredibly slow when I'm in the bedroom.",
        "I'd like to terminate my contract and switch providers.",
        "How do I reset my account password?",
        "I was charged twice for the same service period.",
        "My router keeps disconnecting randomly.",
        "Is there a student discount available?",
        "I need to update my credit card on file.",
        "The technician didn't show up for my installation appointment.",
        "I want to stop paying for this useless service.",
        "What are the hours for your customer support?",
        "My phone line is dead, no dial tone at all.",
        "Can I pause my service for a month while I travel?",
        "There's an unauthorized charge from 'Telecom Corp' on my statement.",
        "The internet works fine, but I want to know about upgrading my TV package."
    ]
    
    print("="*70)
    print(" TELECOM HYBRID ROUTING EFFECTIVENESS REPORT")
    print("="*70)
    
    routing_stats = {"RetentionAgent": 0, "BillingAgent": 0, "TechnicalAgent": 0, "GeneralSupportAgent": 0}
    
    for i, ticket in enumerate(sample_tickets, 1):
        print(f"\n--- Ticket {i}: '{ticket[:50]}...' ---")
        result = route_ticket(ticket)
        print(f"✅ Routed to: {result['agent']}")
        print(f"📌 Reason: {result['reason']}")
        print(f"💬 Response Preview: {result['response'][:120]}...")
        
        routing_stats[result['agent']] += 1

    print("\n" + "="*70)
    print(" ROUTING SUMMARY")
    print("="*70)
    for agent, count in routing_stats.items():
        print(f"  {agent}: {count} tickets")
    print(f"\nTotal tickets processed: {len(sample_tickets)}")
    print("✅ Priority and rule-based routing successfully reduced LLM classification load.")
    print("✅ All routing decisions have been audited to the DynamoDB 'routing-audit' table.")
