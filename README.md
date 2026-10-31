# Telecom Hybrid Routing Agent

> **You are ready to step into the role of an AI traffic controller and build systems that direct complex workflows with precision and speed.**

## The Challenge: Multi-Agent Routing
Imagine a bustling hospital triage desk or a massive international shipping hub. Every incoming request must be sent to the exact right specialist, instantly. If a patient arrives with a simple scrape, they do not need the chief of surgery. If a package is marked "urgent," it bypasses the standard sorting lines. **Multi-agent AI systems face this exact same challenge.**

When you build applications with multiple specialized agents—such as one agent for handling refunds, one for troubleshooting technical errors, and one for fraud detection—you need a reliable way to direct user requests to the correct expert. You *could* send every single message to an advanced Large Language Model to evaluate where it belongs, but that becomes slow, expensive, and inefficient.

## The Solution: Hybrid Routing Architecture
Instead of relying solely on LLMs, the most effective systems use **hybrid routing**. This approach combines fast, deterministic programming rules for predictable requests with the advanced reasoning power of generative AI for complex, ambiguous situations.

In this project, I designed a multi-tier routing architecture to act as an automated support desk router for a major telecom provider. By optimizing for both speed and accuracy using the **Amazon Bedrock API**, the system ensures that high-stakes traffic is handled instantly while ambiguous inputs are safely evaluated by AI.

## 🎯 Key Features & Learning Outcomes
By building this system, this project demonstrates the ability to:
*   **Build a hybrid routing architecture** that directs incoming user requests to specific specialized agents (Billing, Technical, Retention, and General Support).
*   **Create rule-based and priority-based filters** to process predictable and high-stakes traffic (like cancellation requests) efficiently, bypassing the LLM to save latency and costs.
*   **Implement LLM-driven classification** using the Amazon Bedrock API to evaluate and route ambiguous inputs safely, complete with confidence scoring.
*   **Architect secure audit logging** using Amazon DynamoDB to track every routing decision for compliance and observability.

## 🛠️ Tech Stack & Key Resources
This project leverages the following technologies and patterns:
*   **Python `re` module:** Used for Regular Expression Operations to power the deterministic `ROUTING_RULES` and `PRIORITY_PATTERNS`.
*   **Amazon DynamoDB (TTL):** Utilized for the audit logging pattern, leveraging Time to Live (TTL) for auto-deletion of old routing logs.
*   **AWS Nova Lite Model:** The foundational model used via Amazon Bedrock for all LLM-driven intent classifiers in this architecture.
*   **Strands Agents SDK:** Used to instantiate and manage the specialized worker agents with strict system prompt boundaries.

## 🚀 Getting Started
1. Clone the repository: `git clone https://github.com/YOUR_USERNAME/telecom-router.git`
2. Install dependencies: `pip install strands-agents strands-agents-tools boto3 python-dotenv`
3. Deploy the infrastructure: `aws cloudformation deploy --template-file infrastructure/stack.yaml --stack-name lesson-05-exercise-routing`
4. Add your AWS credentials to a `.env` file.
5. Run the router: `python telecom_router.py`

## 📊 Sample Execution Report
A full terminal output from processing 20 sample tickets is available in [`routing_report.txt`](./routing_report.txt). This demonstrates:
- ✅ Priority routing catching cancellation intents immediately
- ✅ Rule-based routing handling clear billing/technical tickets without LLM calls
- ✅ LLM fallback classifying ambiguous tickets with confidence scores
- ✅ DynamoDB audit logging of every routing decision
