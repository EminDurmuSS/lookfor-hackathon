# Lookfor Hackathon Case Description

LLMs, AI, AGI, Agentic AI… Nowadays, we hear these terms more than almost any other. They represent an astonishing shift from our old intuition about what binary systems can do. How can enormously large amounts of multiplication, summation, and non-linearity (activations) feel like human-like reasoning? No words.

Among these concepts, **LLMs** stand at the heart of text-based transformation. From our point of view, the most important thing this popular capability unlocks is the ability to convert **unstructured data and opinions** into **structured outputs**.

We are careful, though. We feel that attaching too much meaning to AI can easily become more than optimism, it can lead us to forget older, valuable principles that still play a critical role in software products. A conservative approach does not mean we are hopeless. It simply means we take the AI layer seriously, but we also take reliability, usability, and engineering discipline seriously.

Of course, we are grateful to the scientists who believed in deep learning from the very beginning, often while their colleagues laughed at them, and made these capabilities available to all of us. Despite all concerns, even only the capability of extracting abstractions from unstructured text is extraordinary and can create enormous welfare.

We could talk about this forever, and we should, let’s do it at the hackathon. But let’s end this narrative here and move to the pragmatic side of what we call AI: what Lookfor is building, and how it contributes to the real-world value created by these developments.

---

## Provider vs. Consumer

In this early era, there are two main ways to interact with AI.

- **Inference providers**
- **Inference consumers**

At Lookfor, we classify ourselves as the latter, at least for now, with the hope of being both at some point.

The hardness of being a provider is obvious: it requires expert-level theoretical knowledge, deep practical experience, and huge amounts of hardware, which means money (so much that even the biggest labs and companies struggle with funding). Luckily, if you are not one of the few teams building foundation models, you don’t need to carry that weight.

But do not relax too early.

Being an inference consumer is also not easy. On this side of the river, we typically see three generic groups.

- **Direct consumers** (e.g., you asking something to Gemini)
- **Consultants** (e.g., n8n / automation freelancers)
- **Tech and platform providers** (what people call LLM wrappers today: Retell, Momentic, Artisan, Lovable, Cursor, Lookfor, etc.)

What wrappers do today is essentially retailing: providers produce the fabric, and we tailor it to the problems we solve and to the profile of the users we serve.

And contrary to popular belief, good old software engineering principles still apply, maybe even more than before, because AI introduces new intangible requirements: latency, uncertainty, evaluation, traceability, safety boundaries, and the need to handle failure gracefully.

AI is only a tool to achieve your purpose, not the purpose itself. So almost always, you still need all the features (or their AI replacements) that your pre-AI competitors already have.

---

## What Lookfor Does

If you decided to participate in our hackathon, you probably already have an idea of what Lookfor does. Still, for completeness, let’s summarize.

At Lookfor, we build a communication platform for e-commerce brands.

Every brand wants a strong tie with their customers.

- Solve their problems
- Understand how they feel about new products
- Learn why they stopped purchasing
- Understand what they need today

This is possible when you have a few customers. But at scale, it becomes impossible without spending enormous resources.

What we unlock using AI is making **long-term, strong relations** between customers and high-growth brands **scalable**.

Now you know what we do, let’s step into how.

---

## Multi-Agent Systems (MAS)

Again, if you joined this hackathon, you already know, but…

**Multi-agent systems (MASs)** are teams of agents that collaborate to achieve a shared objective. Instead of having one agent handle everything, MASs allow you to split responsibilities across multiple agents and define how they work together.

**Agents**, or AI agents, are the fundamental building blocks of a multi-agent system. Each agent acts as a dedicated proxy for an LLM. It comes with its own set of tools and context, allowing it to carry out a specific responsibility within the system.

In this analogy:

- The **LLM** is the agent’s **brain**
- The **tools** are its **hands**
- The **context** is its **eyes**

Together, they enable the agent to understand the situation and take the right actions.

Multi-agent systems sit at the heart of our platform. Merchants tailor their own multi-agent teams according to their needs and assign them to their channels or campaigns for automation.

So far so good.

However, we have a big problem hidden behind the story we’ve just told you.

---

## The Problem Behind the Story

Merchants, customer relationship managers, support representatives, operations teams, are not the best AI workflow builders.

To show the best value to them, which is the only way to win and retain a brand, we often end up creating and maintaining their MASes ourselves as the Lookfor team.

It was cool in the beginning. But as our customer base grows, this becomes a large part of our daily routine.

We study their past customer interactions (e.g., tickets in their old customer relations platform), understand their operations, configure the necessary API tools based on their workflow (e.g., subscription management, inventory systems), and eventually design or update their MAS, test it, and deploy it.

What’s worse is that this takes time, often around **1–3 weeks**, and our sales pipeline gets stuck because onboarding is blocked by workflow design.

The problem is obvious now.

- We built a system that automates customer workflows (step one), and we more or less achieved that.
- The next step is to build a system that automates the creation of systems that automate customer workflows.
- But one needs to be proficient at step one before moving to step two.

That is exactly what this hackathon is about.

---

## Your Task in This Hackathon

You will replicate **step one**, given a merchant’s data.

Normally, when a brand starts to work with Lookfor:

- They send us their previous tickets
- They send a document explaining the workflows they want to automate, including policies, boundaries, and implementation steps (we call this the **workflow manual**)
- They tell us which external tools they use and need in those workflows

Then the Lookfor team integrates those tools and creates their multi-agent workflows accordingly.

Now imagine Lookfor has gained a brand that is an **8-figure subscription business**.

In this hackathon, you will be given the following for that brand:

 **1. Tickets** from their old platform (format is defined, dataset will be provided on-site)

1. **Workflow manual  (**https://docs.google.com/spreadsheets/d/1vMUpkH7v1Aj1Hm0D_aXfFEaKP71RlPeuIv8mj2elcA4/edit?usp=sharing)
2. Hackathon Tool Catalog

Your goal is to build a **multi-agent system** that achieves the desired outcomes described in the workflow manual.

There is almost no limitation on language, platform, frameworks, or user interface expectations.

However, regardless of those details, your program must support the following.

---

## Minimum Requirements

### 1) Email Session Start

We are replicating automation of a brand’s **email support channel**.

In real life, when a brand receives an email, they already know who the customer is (or can identify them). That is why, at the beginning of each session, we will provide you the information you would normally have in a real email support flow.

Your program must support starting a new email session by accepting:

- **Customer email**
- **First name**
- **Last name**
- **Shopify customer ID**

Because this is a prototype, these details will be passed to you at session start.

### 2) Inquiry Handling with Continuous Memory

Your program must:

- Accept the customer’s first message and generate a reply using the multi-agent system you built
- Accept additional new messages in the **same session**
- Maintain **continuous memory** so the system remembers earlier context, does not contradict itself, and behaves like a real email thread

### 3) Observable Answers and Actions

Your system must make answers and actions **observable** during evaluation.

At minimum, for each session, we should be able to inspect:

- The **final message** sent to the customer
- Any **tools called**, including inputs and outputs
- Any **actions taken** as a result of tool calls (refund initiated, subscription paused, address updated, etc.)

A clear trace or timeline of agent decisions is a strong plus.

This can be shown via UI, logs, structured traces, or a simple console output, but it must be clear and easy to inspect.

### 4) Escalation Mechanism

You must implement an escalation mechanism to be used when required by the workflow manual, or when the system cannot safely proceed.

When escalation happens, your system must:

- Inform the customer that the issue is being escalated
- Create a short summary for the team (**structured output is preferred**)
- Stop automatic answer generation for the rest of that session (no further automatic replies)

---

## Provided Ticket Format

Tickets will be provided as an array of objects:

```json
[
  {
    "conversationId": "<C9ADE635-25BC-4865-9263-DC12004FCCB7@gmail.com>",
    "customerId": "cust_1f9a2c8b",
    "createdAt": "19-Jul-2025 14:41:21",
    "ConversationType": "email",
    "subject": "NATPAT Order #NP1380209",
    "conversation": "Customer's message: \"Where's my order...\" Agent's message: \"Hi there...\""
  }
]
```

---

## Tooling Specification

### Uniform API Response Contract

All endpoints return **HTTP 200** (hackathon simplification).

- Success

```json
{ "success": true }
```

or

```json
{ "success": true, "data": {} }
```

- Failure

```json
{ "success": false, "error": "Human-readable explanation" }
```

### Tool Availability

- **Tool endpoints will be available during team evaluation**
- During development, you should rely on the provided specifications for:
    - endpoint details
    - tool input types
    - tool output types

---

## Resources

You will receive API credits on-site for your selected provider:

- OpenAI
- Anthropic
- Google

---

## Evaluation

We will evaluate projects on the following dimensions.

### 1) Workflow Correctness

- Does the system follow the **workflow manual**
- Does it apply **boundaries and policies** correctly
- Does it behave consistently across a **multi-message session**

### 2) Tool Use Quality

- Correct tool selection and correct parameters
- Minimal, purposeful tool usage
- Clear handling of tool failures (`success: false`)
- Correct mapping from tool output to customer response and next steps

### 3) Customer Experience

- Helpful, clear, and safe responses
- Good tone and communication
- Appropriate confirmations when actions are taken (refund, cancel, skip, etc.)

### 4) Escalation Behavior

- Correct triggers based on the workflow manual or uncertainty
- Good customer message plus a good internal summary
- Automation stops after escalation

### 5) Presentation

Teams will present their system during evaluation. (~2 mins)

### 6) System Design

- Code quality
- Workflow design and agent separation
- Routing and orchestration approach
- Observability and tracing
- UI and UX clarity

---

## Submission Expectations

Your submission must include a **runnable program** on **GitHub**. 

- Repository name `Lookfor_Hackathon_2026_{YOUR_TEAM_NAME}
    - Team names were already assigned and will be on your name tag
- Provide the **link** to your repository in your submission
- Include a README explaining:
    - **How to run it**
        - Docker is strongly recommended since it makes evaluation easy
    - **High-level architecture**
        - agents
        - routing
        - retrieval
        - tool calls
    - **How escalation is implemented**

We strongly recommend your project is runnable with a single command (for example, `docker compose up`) and includes environment variable documentation.

- We will provide `API_URL` on site

---

## Closing Note

This hackathon is about building step one properly: taking messy real-world inputs (tickets plus workflow manual) and producing a multi-agent system that can reliably automate a brand’s email workflows, with correct tool usage, correct boundaries, continuous memory, and safe escalation.

Let’s build, argue, and learn together.