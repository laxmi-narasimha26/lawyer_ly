# Implementation Plan - Advanced India Legal Knowledge Base & RAG System

## Overview

This implementation plan converts the comprehensive design into actionable coding tasks for building a production-grade Advanced India Legal Knowledge Base & RAG System. The system will process BNS Act 45 of 2023 and Supreme Court judgments from 2020 (testing phase) with sophisticated legal-aware chunking, hybrid search, and advanced RAG capabilities.

The implementation incorporates critical upgrades identified during design review to ensure Harvey-class accuracy and reliability for Indian legal professionals.

## Task List

- [x] 1. Set up Core Infrastructure and Database Schema


  - Create PostgreSQL database with PGVector extension
  - Implement HNSW indexes with optimized parameters
  - Set up separate collections for statutes and cases
  - Create cross-reference graph storage
  - _Requirements: 7.1, 7.4, 7.5_

- [x] 1.1 Configure PostgreSQL with PGVector Extension


  - Install and configure PostgreSQL with PGVector extension
  - Create database schema for statute_chunks and case_chunks tables
  - Implement HNSW indexes with M=16, ef_construction=200, ef_search=128
  - Add metadata indexes for temporal and keyword filtering
  - _Requirements: 7.4, 7.5_

- [x] 1.2 Create Cross-Reference Graph Storage

  - Design and implement cross_references table for legal relationships
  - Create indexes for efficient graph traversal queries
  - Implement authority weight storage for source ranking
  - Add relationship type classification (statute-to-statute, judgment-to-statute, judgment-to-judgment)
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 1.3 Set up Caching Infrastructure


  - Configure Redis for query embedding cache (LRU 10-50k capacity)
  - Implement result cache with 1-6 hour TTL for hot queries
  - Create document cache for core legal documents (Constitution, major acts)
  - Add cache invalidation mechanisms for knowledge base updates
  - _Requirements: 14.1, 14.2, 14.3, 14.4_

- [x] 2. Implement Document Processing Pipeline with Legal-Aware Chunking






  - Build BNS statute processor with section boundary detection
  - Create Supreme Court judgment processor with paragraph-level extraction
  - Implement deduplication and boilerplate removal
  - Add embedding generation with OpenAI text-embedding-3-large
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2_

- [x] 2.1 Build BNS Statute Processor




  - Implement PDF text extraction with structure preservation
  - Create legal unit parser for Section/Sub-section/Illustration/Explanation/Proviso
  - Generate canonical IDs following BNS:2023:Sec:<number>[:Sub:<clause>] pattern
  - Extract cross-references and create citation links
  - Set effective_from as "2024-07-01" and effective_to as null
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_



- [x] 2.2 Build Supreme Court Judgment Processor


  - Implement paragraph boundary detection using numbering markers
  - Create canonical IDs following SC:<YYYY>:<NeutralOrSCR>:<Slug>:Para:<number> pattern
  - Classify paragraphs into Facts/Issues/Analysis/Held/Order/Citations sections
  - Extract case metadata (bench, decision date, case title, citations)
  - Normalize statute references to canonical IDs (e.g., "Section 147 BNS" → "BNS:2023:Sec:147")
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 2.3 Implement Deduplication and Boilerplate Removal


  - Remove page headers/footers and reporter boilerplate from extracted text
  - Detect and remove identical headnote repeats and OCR noise
  - Track SHA256 per chunk and skip re-embedding unchanged spans
  - Implement content quality filters to exclude non-substantive text


  - Create preprocessing pipeline for clean text before tokenization
  - _Requirements: 7.1, 7.2_

- [x] 2.4 Create Embedding Generation Service


  - Integrate OpenAI text-embedding-3-large model for 1536-dimension vectors
  - Implement batch processing for efficient API usage
  - Add embedding caching to reduce API costs
  - Create embedding validation and quality checks
  - Implement retry logic with exponential backoff for API failures
  - _Requirements: 7.3, 14.5_

- [x] 3. Build Hybrid Search Engine with Legal Optimizations




  - Implement dense vector similarity search using HNSW
  - Create sparse keyword search with BM25 and legal synonyms
  - Build re-ranking system with relevance, authority, and recency weights
  - Add MMR for result diversification
  - _Requirements: 3.1, 3.2, 3.3, 3.4_



- [x] 3.1 Implement Dense Vector Similarity Search
  - Create vector search service using PGVector HNSW indexes
  - Implement efficient similarity computation with L2 normalized embeddings
  - Add metadata filtering for temporal scope and document type
  - Configure search parameters: k=50 for cases, k=20 for statutes
  - Optimize query performance for sub-800ms retrieval target


  - _Requirements: 3.1, 6.2_

- [x] 3.2 Create Sparse Keyword Search with Legal Synonyms
  - Implement BM25 full-text search using PostgreSQL gin indexes
  - Create legal synonym dictionary (FIR, cognizable, non-bailable, remand, SLP, anticipatory, locus, obiter, ratio, per incuriam)
  - Add exact match boosting for case citations and section numbers
  - Implement query expansion with legal terminology
  - Configure analyzers for Indian legal text processing
  - _Requirements: 3.2, 9.2, 9.3, 19.1, 19.2_

- [x] 3.3 Build Re-Ranking System with Authority Weights
  - Implement re-ranking algorithm with configurable weights (relevance 0.6, statute-edge 0.25, recency/authority 0.15)
  - Create authority scoring system (BNS bare act > unofficial mirror, Supreme Court > High Courts)
  - Add cross-reference graph boosting for related documents
  - Implement temporal preference for recent judgments
  - Configure final result selection: top-8 mixed (max 4 statutes + 4 cases)
  - _Requirements: 3.3, 3.4, 8.5_

- [x] 3.4 Add MMR for Result Diversification
  - Implement Maximal Marginal Relevance with λ=0.7
  - Balance relevance and diversity in final result set
  - Prevent near-duplicate results from dominating output
  - Merge overlapping chunks from same document
  - Ensure comprehensive coverage across different legal authorities
  - _Requirements: 3.4_

- [ ] 4. Implement Temporal Validity and As-On Date Reasoning
  - Create temporal filtering for statutes and case law
  - Build as-on date extraction from user queries
  - Implement effective date management for legal provisions
  - Add BNS ⇄ legacy IPC/CrPC mapping layer
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 4.1 Create Temporal Filtering System
  - Implement as-on date extraction from user queries (default: current date)
  - Filter statute sections by effective_from and effective_to dates
  - Prioritize case law decided on or before as-on date
  - Create temporal scope validation for legal accuracy
  - Display as-on date used in generated answers
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 4.2 Build BNS ? Legacy IPC/CrPC Mapping Layer
  - Create mapping table for BNS sections to legacy IPC/CrPC sections
  - Implement query routing for legacy section references (e.g., "IPC 378 theft" → BNS equivalent)
  - Add reverse mapping for historical queries
  - Surface redirection notes when legacy terms are mapped
  - Maintain bidirectional compatibility for user queries
  - _Requirements: 5.5_

- [ ] 4.3 Implement Effective Date Management
  - Create system for tracking statute amendments and corrigenda
  - Implement effective_to date updates when sections are superseded
  - Add version control for legal provisions
  - Create Gazette watcher framework for automated updates
  - Maintain historical accuracy for temporal queries
  - _Requirements: 20.2, 20.4_

- [ ] 5. Build Query Understanding and Legal Context Processing
  - Create query analysis service for legal terminology detection
  - Implement legal synonym expansion
  - Add section number guessing for offense queries
  - Build temporal intent extraction
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 5.1 Create Query Analysis Service
  - Implement legal terminology detection and classification
  - Extract temporal intent from queries ("as on 2021", "current law")
  - Identify offense keywords and procedural terms
  - Classify query types (factual, comparative, procedural)
  - Generate section number guesses for common offenses (e.g., "robbery" → BNS:Sec:147)
  - _Requirements: 9.1, 9.2, 9.4_

- [x] 5.2 Implement Legal Synonym Expansion
  - Create comprehensive legal synonym dictionary
  - Expand procedural terms (FIR, cognizable, non-bailable, remand, SLP, anticipatory)
  - Add judicial terminology (locus, obiter, ratio, per incuriam)
  - Implement context-aware synonym selection
  - Configure synonym weights for retrieval optimization
  - _Requirements: 9.2, 9.3, 19.2_

- [x] 5.3 Build Clarification and Refusal Logic
  - Implement insufficient context detection
  - Create clarifying question generation (limit: 1 question)
  - Add refusal logic when legal elements cannot be matched to facts
  - List missing facts needed for complete analysis
  - Avoid speculation on ambiguous legal queries
  - _Requirements: 9.5, 12.1_

- [ ] 6. Create Context Assembly and Token Management
  - Build context assembler with statute and case blocks
  - Implement token limit management (75% context, 25% response)
  - Add source ID and quote span marker insertion
  - Create overlapping chunk merging
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 6.1 Build Context Assembler
  - Create separate STATUTE and CASE blocks for LLM context
  - Implement token counting and limit management (≤75% of model window)
  - Insert source IDs and quote span markers for citation tracking
  - Merge overlapping chunks to reduce redundancy
  - Prioritize highest-scoring chunks when context exceeds limits
  - _Requirements: 11.1, 11.2, 11.3, 11.5_

- [x] 6.2 Implement Token Management System
  - Create accurate token counting for different model types
  - Reserve ≥25% of model window for generated response
  - Implement intelligent truncation when context exceeds limits
  - Add context optimization to maximize relevant information
  - Monitor token usage for cost optimization
  - _Requirements: 11.2, 11.4_

- [x] 7. Implement Answer Generation with Legal Precision
  - Create prompt engineering for legal accuracy
  - Implement temperature control (0.2 for factual, 0.5 for comparative)
  - Add citation requirement enforcement
  - Build response post-processing
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 7.1 Create Legal Prompt Engineering
  - Design system prompts for legal accuracy and citation requirements
  - Implement temperature control: 0.2 for factual queries, 0.5 for comparative analysis
  - Enforce citation requirement for each material claim
  - Add instructions for verbatim quotes (≤300 characters)
  - Create mode-specific prompt templates
  - _Requirements: 10.1, 10.2, 10.3_

- [x] 7.2 Build Response Post-Processing
  - Implement citation formatting according to Indian legal conventions
  - Extract and validate quoted text from responses
  - Format source references with canonical IDs
  - Add disclaimer for uncertain information
  - Create response quality validation
  - _Requirements: 10.4, 10.5_

- [x] 8. Implement Hallucination Detection and Citation Verification
  - Build claim verification against retrieved sources
  - Create quote-span round-trip validation
  - Implement citation existence checking
  - Add response regeneration logic for failed verification
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 8.1 Build Claim Verification System
  - Extract factual claims from generated responses
  - Verify each claim is supported by retrieved source chunks
  - Implement confidence scoring for claim support
  - Flag unsupported claims for removal or disclaimer
  - Create claim-to-source mapping for transparency
  - _Requirements: 4.1, 4.2_

- [x] 8.2 Create Quote-Span Round-Trip Validation
  - Implement exact string matching for quoted text
  - Normalize whitespace and punctuation for comparison
  - Verify all quotes appear exactly in retrieved chunks
  - Auto-retry with expanded k when validation fails
  - Return "insufficient support" message for persistent failures
  - _Requirements: 4.3, 4.5_

- [x] 8.3 Build Citation Existence Checking
  - Verify citation IDs exist in knowledge base
  - Check citation accessibility and URL validity
  - Cross-reference citations against external legal databases
  - Implement citation correction suggestions
  - Log citation verification results for quality monitoring
  - _Requirements: 4.3, 4.4_

- [x] 8.4 Implement Response Regeneration Logic
  - Create retry mechanism with expanded retrieval (k↑) for failed verification
  - Implement maximum retry limit (2 attempts)
  - Generate refusal messages with specific missing facts
  - Add user guidance for query refinement
  - Log regeneration events for system optimization
  - _Requirements: 4.5, 12.2_

- [x] 9. Build Performance Optimization and Caching
  - Implement intelligent caching strategies
  - Optimize database queries and connections
  - Add performance monitoring and alerting
  - Create load balancing and scaling mechanisms
  - _Requirements: 6.1, 6.2, 6.3, 14.1, 14.2_

- [x] 9.1 Implement Intelligent Caching Strategies
  - Create query embedding cache with LRU eviction (10-50k capacity)
  - Implement ANN result cache for hot queries (1-6 hour TTL)
  - Add permanent in-memory cache for core legal documents
  - Create cache invalidation for knowledge base updates
  - Monitor cache hit rates and optimize cache policies
  - _Requirements: 14.1, 14.2, 14.3, 14.4_

- [x] 9.2 Optimize Database Performance
  - Implement connection pooling for PostgreSQL
  - Create read replicas for query distribution
  - Optimize HNSW index parameters for production load
  - Add query performance monitoring and slow query logging
  - Implement database maintenance procedures
  - _Requirements: 17.2, 17.3_

- [x] 9.3 Create Performance Monitoring System
  - Track response times for all system components
  - Monitor vector search time, LLM API call time, and total response time
  - Implement alerting for performance degradation
  - Create cost monitoring for OpenAI API usage
  - Add system health checks and uptime monitoring
  - _Requirements: 6.1, 6.2, 16.3, 16.4_

- [ ] 10. Create Evaluation and Quality Assurance System
  - Build golden set of legal Q&A pairs
  - Implement accuracy metrics (Hit@3 for statutes, Hit@5 for cases)
  - Create automated testing pipeline
  - Add performance benchmarking
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [ ] 10.1 Build Golden Set Evaluation Framework
  - Create 150+ legal Q&A pairs across BNS offenses, bail, electronic evidence, Article 14/21
  - Implement automated evaluation pipeline with expected sections and cases
  - Track Hit@3 accuracy for statute retrieval (≥95% target)
  - Track Hit@5 accuracy for case retrieval (≥90% target)
  - Monitor citation correctness (100% URL presence and quote matching)
  - _Requirements: 13.1, 13.2, 13.3_

- [ ] 10.2 Create Performance Benchmarking System
  - Implement latency testing for p95 ≤3-6 seconds end-to-end
  - Create concurrent load testing (simulate multiple users)
  - Monitor retrieval performance (≤800ms target)
  - Track embedding generation and caching efficiency
  - Add regression testing for system updates
  - _Requirements: 6.1, 6.2, 13.4_

- [ ] 10.3 Build Quality Assurance Dashboard
  - Create real-time metrics dashboard for accuracy and performance
  - Implement golden set replay functionality
  - Add delta tracking for system improvements
  - Create alerting for quality regressions
  - Generate quality reports for stakeholder review
  - _Requirements: 13.5_

- [ ] 11. Implement Security and Data Privacy
  - Add data encryption at rest and in transit
  - Implement secure API authentication
  - Create audit logging without sensitive content
  - Add privacy controls and compliance features
  - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

- [ ] 11.1 Implement Data Encryption and Security
  - Configure encryption at rest for PostgreSQL and Redis
  - Implement HTTPS/TLS for all API communications
  - Secure OpenAI API credentials using environment variables
  - Add input validation and SQL injection prevention
  - Create secure session management
  - _Requirements: 15.1, 15.3_

- [ ] 11.2 Create Audit Logging System
  - Log query IDs, document IDs, response times, and success status
  - Implement structured logging without sensitive content exposure
  - Create audit trails for system access and operations
  - Add compliance reporting capabilities
  - Monitor for suspicious activity patterns
  - _Requirements: 15.4, 16.1, 16.2_

- [ ] 12. Build Monitoring and Observability
  - Implement comprehensive logging and metrics
  - Create alerting for system health issues
  - Add cost tracking and optimization
  - Build operational dashboards
  - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

- [ ] 12.1 Create Comprehensive Logging System
  - Implement structured logging for all system components
  - Log error messages, stack traces, and request context
  - Track performance metrics and API usage
  - Create log aggregation and search capabilities
  - Add log retention and archival policies
  - _Requirements: 16.1, 16.2, 16.3_

- [ ] 12.2 Build Alerting and Monitoring
  - Create alerts for high error rates and slow response times
  - Monitor system resource usage and capacity
  - Track OpenAI API costs and usage patterns
  - Implement health checks for all services
  - Add automated incident response procedures
  - _Requirements: 16.4, 16.5_

- [ ] 13. Create Update Pipeline and Maintenance System
  - Build automated document ingestion pipeline
  - Implement weekly Supreme Court case synchronization
  - Create BNS amendment tracking system
  - Add index maintenance and optimization
  - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5_

- [ ] 13.1 Build Automated Document Ingestion Pipeline
  - Create ETL scripts for processing new legal documents
  - Implement batch processing with parallel execution
  - Add document validation and quality checks
  - Create ingestion monitoring and error handling
  - Support multiple document formats (PDF, HTML, text)
  - _Requirements: 20.1, 20.5_

- [ ] 13.2 Implement Weekly Case Synchronization
  - Create SHA256-based change detection for Supreme Court cases
  - Implement incremental updates to minimize processing costs
  - Add automated download and processing of new judgments
  - Create synchronization monitoring and reporting
  - Handle failed downloads and processing errors gracefully
  - _Requirements: 20.1, 20.3_

- [ ] 13.3 Create BNS Amendment Tracking System
  - Build Gazette watcher for BNS updates and corrigenda
  - Implement effective_to date updates for superseded sections
  - Add new version processing and indexing
  - Create amendment notification system
  - Maintain historical accuracy for temporal queries
  - _Requirements: 20.2, 20.4_

- [ ] 13.4 Add Index Maintenance and Optimization
  - Implement nightly incremental index updates
  - Create quarterly full index compaction procedures
  - Add HNSW index optimization and rebalancing
  - Monitor index performance and fragmentation
  - Create automated maintenance scheduling
  - _Requirements: 20.3, 20.5_

- [ ] 14. Build API and User Interface
  - Create RESTful API endpoints for query processing
  - Implement user authentication and session management
  - Build web interface for legal professionals
  - Add administrative dashboard for system management
  - _Requirements: 6.1, 6.2, 17.1, 17.4_

- [ ] 14.1 Create RESTful API Endpoints
  - Implement /api/v1/query endpoint for legal question processing
  - Create /api/v1/documents endpoints for document management
  - Add /api/v1/citations endpoint for citation retrieval
  - Implement rate limiting and request validation
  - Create comprehensive API documentation
  - _Requirements: 17.1_

- [ ] 14.2 Build Web Interface for Legal Professionals
  - Create responsive chat interface for legal queries
  - Implement document upload and management features
  - Add citation viewer with source text display
  - Create user preferences and settings management
  - Build help and documentation sections
  - _Requirements: 17.4_

- [ ] 14.3 Add Administrative Dashboard
  - Create system health and performance monitoring interface
  - Implement user management and access control
  - Add knowledge base management tools
  - Create evaluation and testing interfaces
  - Build system configuration management
  - _Requirements: 17.1_

- [ ] 15. Testing and Validation with 2020 Supreme Court Data
  - Process and index 2020 Supreme Court dataset (1,664 documents, 233 MB)
  - Validate BNS processing with complete act
  - Test retrieval accuracy with focused legal queries
  - Verify performance requirements with test dataset
  - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_

- [ ] 15.1 Process 2020 Supreme Court Dataset
  - Ingest and process 1,664 Supreme Court PDFs from 2020 (233 MB total)
  - Apply paragraph-level chunking and citation extraction
  - Generate embeddings and create HNSW indexes
  - Validate processing quality and completeness
  - Create test dataset statistics and quality reports
  - _Requirements: 18.1, 18.4_

- [ ] 15.2 Validate BNS Processing
  - Process complete BNS Act (a2023-45.pdf) with legal-aware chunking
  - Verify section boundary detection and canonical ID generation
  - Test cross-reference extraction and citation linking
  - Validate effective date assignment and temporal filtering
  - Create BNS processing quality assessment
  - _Requirements: 18.2_

- [ ] 15.3 Test Retrieval Accuracy with Legal Queries
  - Create test queries for robbery, theft, cheating, and other BNS offenses
  - Validate correct section identification and ranking
  - Test hybrid search performance with legal terminology
  - Verify citation accuracy and quote matching
  - Measure Hit@3 and Hit@5 accuracy rates
  - _Requirements: 18.3, 18.5_

- [ ] 15.4 Verify Performance Requirements
  - Test end-to-end response times with 2020 dataset
  - Validate sub-6-second response time requirement
  - Test concurrent user load and system scalability
  - Measure retrieval performance (≤800ms target)
  - Create performance baseline for production scaling
  - _Requirements: 18.4_

- [ ] 16. Create Documentation and Deployment Guide
  - Write comprehensive system documentation
  - Create deployment and operations guide
  - Build user manual for legal professionals
  - Add developer documentation and API guides
  - _Requirements: 17.5_

- [ ] 16.1 Write System Documentation
  - Create architecture overview and component documentation
  - Document database schema and data models
  - Write configuration and deployment procedures
  - Create troubleshooting and maintenance guides
  - Add system monitoring and alerting documentation
  - _Requirements: 17.5_

- [ ] 16.2 Create User Manual for Legal Professionals
  - Write user guide for chat interface and query formulation
  - Document citation interpretation and source verification
  - Create best practices guide for legal research
  - Add FAQ section for common questions
  - Build tutorial videos and training materials
  - _Requirements: 17.5_

- [ ] 16.3 Build Developer Documentation
  - Create API documentation with examples and use cases
  - Write code documentation and inline comments
  - Document extension and customization procedures
  - Create contribution guidelines for open source development
  - Add testing and quality assurance procedures
  - _Requirements: 17.5_

## Implementation Notes

### Priority Order

1. **Critical Path (Tasks 1-8)**: Core infrastructure, document processing, search, and generation components - ALL REQUIRED
2. **Quality Assurance (Tasks 9-10)**: Performance optimization and evaluation systems - ALL REQUIRED
3. **Production Readiness (Tasks 11-13)**: Security, monitoring, and maintenance systems - ALL REQUIRED
4. **User Interface (Task 14)**: API and web interface development - ALL REQUIRED
5. **Validation (Task 15)**: Testing with 2020 dataset - ALL REQUIRED
6. **Documentation (Task 16)**: Comprehensive documentation and guides - ALL REQUIRED

**All tasks are required for comprehensive production-grade implementation.**

### Key Dependencies

- Task 2 (Document Processing) depends on Task 1 (Infrastructure)
- Task 3 (Hybrid Search) depends on Tasks 1-2
- Tasks 4-8 (Advanced Features) depend on Tasks 1-3
- Task 15 (Testing) requires completion of Tasks 1-8
- All tasks should include appropriate logging and monitoring integration

### Success Criteria

Each task should be considered complete when:

1. All specified functionality is implemented and tested
2. Code follows established patterns and includes comprehensive error handling
3. Performance requirements are met (sub-6-second responses, ≤800ms retrieval)
4. Accuracy requirements are achieved (95% Hit@3 for statutes, 90% Hit@5 for cases)
5. Security and privacy requirements are satisfied
6. Comprehensive logging and monitoring are in place

### Technical Considerations

- Maintain focus on 2020 Supreme Court data for initial testing
- Implement all 10 critical upgrades identified in design review
- Follow production-grade coding practices with comprehensive testing
- Ensure scalability and maintainability for future expansion
- Prioritize accuracy and citation verification over speed optimizations
- Create modular architecture for easy component replacement and upgrades

### Estimated Timeline

- **Tasks 1-3**: 3-4 weeks (Core infrastructure and search)
- **Tasks 4-8**: 4-5 weeks (Advanced features and generation)
- **Tasks 9-10**: 2-3 weeks (Performance and evaluation)
- **Tasks 11-13**: 2-3 weeks (Security and maintenance)
- **Tasks 14-15**: 2-3 weeks (Interface and testing)
- **Task 16**: 1-2 weeks (Documentation)

**Total Estimated Timeline**: 14-20 weeks for complete implementation

This implementation plan provides a comprehensive roadmap for building a Harvey-class legal AI system specifically optimized for Indian law with the BNS and Supreme Court judgment corpus.
