# Checkpoint Preparation Guide

Prepare your module checkpoint by generating rubric reports, crafting a clear module explanation, and beginning your visual presentation.

---

## 1. Rubric Review Reports

### Code Elegance Report

Ask an agent to review your code against the [Code Elegance Rubric](code_elegance_rubric.md). Request that the review include:

- **Summary**: 1-2 sentences capturing the overall quality and main strengths/areas for improvement
- **Findings**: Assessment against each criterion (Naming Conventions, Function Design, Abstraction & Modularity, Style Consistency, Code Hygiene, Control Flow Clarity, Pythonic Idioms)
- **Scores**: Points per criterion (0-4 scale)

**Save as**: `checkpoint_X_elegance_report.md` (replace X with checkpoint number)

### Module Rubric Report

Ask an agent to review your module against the [Module Rubric](module_rubric.md). Request the review include:

- **Summary**: 1-2 sentences on module completeness and alignment with specification
- **Findings**: Assessment against each criterion (Specification Clarity, Inputs/Outputs, Dependencies, Test Coverage, Documentation, Integration Readiness)
- **Scores**: Points per criterion

**Save as**: `checkpoint_X_module_report.md` (replace X with checkpoint number)

---

## 2. Module Explanation (In-Person Demo)

Prepare to clearly explain your module during the in-person presentation. Be ready to discuss:

### Input
- **What does your module accept?** Describe the data structure, format, and constraints
- **Example**: Have a concrete input example ready (e.g., "List of candidate answers: `['answer_1', 'answer_2', ...]`")

### Output
- **What does your module produce?** Describe the data structure and format
- **Next Module Feed**: Clearly articulate how this output becomes input to the next module in the pipeline (or is the final system output)

### AI Concepts
- **What AI techniques are used?** Be prepared to explain the core algorithms or models (e.g., "We use a Knowledge Base and forward chaining to generate new facts", "We use cosine similarity for semantic matching")
- **Why these choices?** Be ready to justify why these concepts fit the problem your module solves

---

## 3. Presentation Best Practice (Optional, but STRONGLY Advised)

**Start your "talk" PowerPoint now** by expressing your module visually. Your slides should include:

- **Data Flow Diagram**: Show how input transforms to output (boxes, arrows, data shapes)
- **Input/Output Visualization**: Concrete visual example of what your module processes and produces
- **AI Concept Illustration**: Visual representation of the algorithm or model (e.g., embedding space, similarity scores, decision tree branches)
- **Integration Point**: Show where this module sits in the overall AI system pipeline

Starting visuals early helps clarify your thinking and ensures your explanation aligns with your implementation.

---

## Checkpoint Readiness Checklist

- [ ] Code elegance report generated and saved as `checkpoint_X_elegance_report.md`
- [ ] Module rubric report generated and saved as `checkpoint_X_module_report.md`
- [ ] Module input clearly documented with concrete example
- [ ] Module output clearly documented with next-module feed specified
- [ ] AI concepts explained with justification
- [ ] PowerPoint presentation started with visual representations
- [ ] All code changes pushed to repository
- [ ] Team participation visible in commit history
