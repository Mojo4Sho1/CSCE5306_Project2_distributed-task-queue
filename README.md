# Distributed Task Queue (Distributed Systems Project)

## Project Goal
Design, implement, and evaluate a distributed task queue system using gRPC and Dockerized nodes.

## Architectures Compared
1. **Microservices design (6 nodes)**  
   - gateway, job, queue, worker, result, load generator
2. **Monolith-per-node design (6 nodes)**  
   - six identical nodes, each running most/all functionality in-process

## Communication Model
- gRPC (Protocol Buffers) for RPC communication.

## Functional Requirements
1. SubmitJob
2. GetJobStatus
3. GetJobResult
4. CancelJob
5. ListJobs
6. WorkerHeartbeat / FetchWork

## Tech Stack
- Python
- grpcio / protobuf
- Docker / Docker Compose
- Git / GitHub

## Current Status
- [x] Repo scaffold initialized
- [ ] Protobuf API defined
- [ ] Microservices MVP implemented
- [ ] Monolith-per-node baseline implemented
- [ ] Benchmark harness implemented
- [ ] Evaluation results generated

## Report
Final report is maintained in Overleaf.
