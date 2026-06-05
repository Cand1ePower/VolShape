# VolShape Remediation Plan

Last updated: 2026-06-05

## P0 Completed

- [x] Split and commit the pending multimodal and nutrition-archive work
- [x] Write down the remediation backlog in a dedicated file
- [x] Fix SSE chat stream DB session lifecycle
- [x] Add upload size limits for image/video analysis
- [x] Replace wildcard CORS with explicit allowed origins
- [x] Add `/health` endpoint for service health checks
- [x] Add a defensive `UserProfile` upsert in the chat message persistence path

## P1 Next

- [ ] Rework ACWR when history is insufficient instead of hardcoding a chronic baseline
- [ ] Add focused tests for ACWR, nutrition scaling/parsing, and completion summarization
- [ ] Clean up remaining encoding/mojibake issues in user-facing/backend prompt text
- [ ] Verify Langfuse trace hierarchy and reduce redundant traces

## P2 Architecture

- [ ] Split `backend/app/api/chat.py` into stream, sessions, and insights modules
- [ ] Add request rate limiting for chat and media endpoints
- [ ] Add containerized local stack polish (`docker-compose`, health-first startup story)
- [ ] Harden Langfuse client initialization with cached/safe singleton construction

## P3 Productization

- [ ] Turn MCP provider plans into executable runtime adapters
- [ ] Expose richer SSE state payloads with key decision details
- [ ] Add admin stats/ops endpoints backed by existing usage tables
- [ ] Expand observability docs and deployment runbooks

## Notes

- The previous audit correctly identified the session lifecycle, upload-size, CORS, and ACWR issues as the highest-value backend fixes.
- `UserProfile` FK risk is already partially mitigated in auth flows, but we still keep a defensive upsert in the central message-save path.
- MCP is currently a provider/factory design layer, not yet the main runtime execution path.
