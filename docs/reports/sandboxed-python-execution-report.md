# Sandboxed Python Code Execution

## Tomoro Research Report

Date: March 13, 2026

### Objective

Evaluate off-the-shelf sandboxed Python execution solutions, including locally containerised approaches, with emphasis on:

- library availability, especially `pandas` and `numpy`
- open-source or free solutions
- setup effort
- security
- operational tradeoffs

### Executive Summary

For workloads that require broad Python library compatibility, the best options are container or VM-backed sandboxes rather than restricted interpreters.

The strongest candidates are:

- Docker-based local execution
- Docker + gVisor
- Judge0 CE
- Piston

Pydantic Monty is worth noting, but it is not a strong fit for `pandas` and `numpy` heavy workloads because third-party package support is intentionally out of scope.

### Top Recommendation

The best overall fit for Tomoro's stated priorities is:

**Docker + gVisor**

This offers:

- strong support for normal Linux Python environments
- straightforward packaging of `numpy`, `pandas`, and related libraries
- stronger isolation than plain containers
- a fully open-source and self-hosted path

### Secondary Recommendations

**Judge0 CE**

- best off-the-shelf self-hosted execution API
- useful when the requirement is an API service rather than direct container orchestration

**Piston**

- lightweight open-source execution engine
- best when a slimmer multi-language execution API is preferred

**Plain Docker**

- easiest and fastest route to full package compatibility
- appropriate if security requirements are moderate and the workload is not highly adversarial

### Evaluation Criteria

- Setup effort
- Availability of scientific Python libraries
- Security boundary strength
- Persistence and runtime flexibility
- Operational complexity
- Cost and openness

### Solution Comparison

| Option | Open source / free | Setup | `numpy` / `pandas` | Security | Best fit |
| --- | --- | --- | --- | --- | --- |
| Local Docker | Yes | Easy | Excellent | Medium | Fastest self-hosted route |
| Docker + gVisor | Yes | Medium | Excellent | High | Best overall balance |
| Judge0 CE | Yes | Medium | Good to high | Good | Self-hosted execution API |
| Piston | Yes | Medium | Good | Good | Lightweight execution engine |
| Firecracker / Kata | Yes | Hard | Excellent | Very high | High-security multi-tenant isolation |
| Pyodide / MCP Run Python | Yes | Easy | Medium to good | High | Bounded execution with compatibility tradeoffs |
| Pydantic Monty | Yes | Very easy | Poor | High in constrained model | Restricted embedded execution |

### Findings

#### Docker

The most practical baseline. Prebuild an image with the exact Python stack required and execute each job inside a fresh constrained container.

Strengths:

- best package compatibility
- free and open source
- simple local setup

Weaknesses:

- standard container isolation is weaker than microVM style boundaries
- secure deployment requires careful hardening

#### Docker + gVisor

The best balance of compatibility, security, and cost. gVisor reduces kernel attack surface while preserving a familiar container workflow.

Strengths:

- excellent package compatibility
- stronger sandboxing than plain Docker
- self-hosted and open source

Weaknesses:

- additional setup and runtime tuning
- occasional compatibility or performance tradeoffs

#### Judge0 CE

A mature open-source code execution platform with an API-first model.

Strengths:

- ready-made self-hosted API
- established open-source project
- practical if the consumer expects submit-and-run semantics

Weaknesses:

- less natural for rich persistent Python sessions
- library coverage depends on runtime packaging choices

#### Piston

A lightweight open-source execution engine with a simpler footprint.

Strengths:

- open source and API-driven
- lighter-weight than a full custom platform

Weaknesses:

- may require extra customization for heavier data-science environments
- not as strong a default recommendation as Docker + gVisor for scientific Python

#### Firecracker / Kata

MicroVM-style solutions provide the strongest isolation but carry the highest operational cost.

Strengths:

- very strong isolation
- can still support standard Python stacks

Weaknesses:

- significantly harder to operate
- usually unnecessary unless the threat model is severe

#### Pyodide / Pydantic MCP Run Python

Useful for safer bounded execution, but not a full replacement for Linux Python.

Strengths:

- strong isolation model
- easy to embed in agent systems
- scientific packages exist in the ecosystem

Weaknesses:

- compatibility is narrower than standard Python on Linux
- not ideal when minimal surprises with native libraries are required

#### Pydantic Monty

A serious but fundamentally different design: a restricted embedded interpreter intended for safe execution of constrained logic.

Strengths:

- excellent safety model for explicit host-function execution
- fast and lightweight
- very easy to integrate

Weaknesses:

- not suitable for arbitrary package ecosystems
- poor fit for `numpy` and `pandas` workloads

### Recommended Architecture

For Tomoro, the most defensible implementation path is:

- prebuilt Python image with required scientific libraries
- fresh execution container per run
- read-only base filesystem where possible
- scratch working directory for job outputs
- CPU, memory, and wall-clock limits
- outbound network disabled by default
- rootless container runtime where feasible
- gVisor for an additional isolation layer

### Final Conclusion

If library availability and open-source freedom are the top priorities, the market points clearly to containerized Linux execution.

Recommended decision order:

1. Docker + gVisor
2. Hardened local Docker
3. Judge0 CE
4. Piston
5. Firecracker or Kata only when the stronger isolation boundary justifies the complexity

### Sources

- https://docs.docker.com/engine/security/rootless/
- https://gvisor.dev/docs/
- https://github.com/judge0/judge0
- https://judge0.com/
- https://github.com/engineer-man/piston
- https://github.com/firecracker-microvm/firecracker
- https://katacontainers.org/
- https://pyodide.org/en/stable/usage/packages-in-pyodide.html
- https://ai.pydantic.dev/mcp/run-python/
- https://pydantic.dev/articles/pydantic-monty
