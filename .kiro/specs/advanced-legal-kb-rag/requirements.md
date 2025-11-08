# Requirements Document

## Introduction

This document outlines the requirements for an Advanced India Legal Knowledge Base & RAG System - a production-grade, state-of-the-art AI system that provides accurate, low-latency answers grounded in Indian legal sources. The system will process the Bharatiya Nyaya Sanhita (BNS) Act 45 of 2023 and Supreme Court judgments (2020-2024) to create a comprehensive legal knowledge base with sophisticated retrieval-augmented generation capabilities. The system prioritizes accuracy, temporal correctness, and deterministic retrieval with sub-3-6 second response times.

## Glossary

- **System**: The Advanced India Legal Knowledge Base & RAG System
- **BNS**: Bharatiya Nyaya Sanhita (Act 45 of 2023) - the new criminal code replacing IPC
- **Knowledge_Base**: Collection of processed and indexed Indian legal documents
- **RAG_Pipeline**: Retrieval-Augmented Generation workflow with hybrid search and re-ranking
- **Vector_Database**: Database storing document embeddings for semantic search (PostgreSQL with PGVector)
- **Hybrid_Search**: Combined dense vector similarity search and sparse BM25 keyword search
- **Legal_Chunk**: Semantically coherent segment of legal text preserving legal boundaries
- **Citation_ID**: Canonical identifier for legal sources (e.g., BNS:2023:Sec:147, SC:2021:CriminalAppeal1234)
- **Temporal_Scope**: Time-based filtering ensuring legal accuracy as-on specific dates
- **Hallucination_Detector**: System component that verifies claims against retrieved sources
- **As_On_Date**: Reference date for determining applicable law and relevant precedents
- **Legal_Unit**: Atomic legal structure (Section, Sub-section, Illustration, Explanation, Proviso)
- **Judgment_Para**: Individual numbered paragraph from Supreme Court judgment
- **Cross_Reference_Graph**: Network of relationships between statutes and case law

## Requirements

### Requirement 1: BNS Statute Processing and Legal-Aware Chunking

**User Story:** As a legal researcher, I want the system to accurately process the BNS Act with proper legal structure recognition, so that I can get precise answers about specific sections and their relationships.

#### Acceptance Criteria

1. WHEN the System processes the BNS PDF (a2023-45.pdf), THE System SHALL split the text into legal units preserving Section, Sub-section, Illustration, Explanation, and Proviso boundaries
2. WHEN creating statute chunks, THE System SHALL assign canonical IDs following the pattern BNS:2023:Sec:<number>[:Sub:<clause>] for each legal unit
3. WHEN storing statute sections, THE System SHALL include effective_from date as "2024-07-01" and effective_to as null for current law
4. WHEN processing cross-references within BNS, THE System SHALL create citation links to referenced sections in the citations field
5. WHEN a statute chunk is created, THE System SHALL store the verbatim text, section title, and hierarchical position within the act

### Requirement 2: Supreme Court Judgment Processing with Paragraph-Level Extraction

**User Story:** As a legal practitioner, I want the system to process Supreme Court judgments with proper paragraph-level chunking, so that I can access specific judicial reasoning and holdings.

#### Acceptance Criteria

1. WHEN the System processes Supreme Court PDFs from 2020, THE System SHALL detect and extract paragraph boundaries using numbering markers like "¶", "(1)", or "1."
2. WHEN creating judgment chunks, THE System SHALL assign canonical IDs following the pattern SC:<YYYY>:<NeutralOrSCR>:<Slug>:Para:<number>
3. WHEN processing judgment sections, THE System SHALL classify paragraphs into categories: Facts, Issues, Analysis, Held, Order, or Citations
4. WHEN extracting case metadata, THE System SHALL identify bench composition, decision date, case title, and citation references
5. WHEN detecting statute references in judgments, THE System SHALL normalize them to canonical IDs (e.g., "Section 147 BNS" → "BNS:2023:Sec:147")

### Requirement 3: Hybrid Search with Legal-Specific Optimization

**User Story:** As a system architect, I want a hybrid search system that combines semantic similarity with legal keyword matching, so that the system finds both conceptually similar content and exact legal citations.

#### Acceptance Criteria

1. WHEN performing retrieval, THE System SHALL combine dense vector similarity search using OpenAI text-embedding-3-large with sparse BM25 keyword search
2. WHEN a query contains legal terms like "robbery", "bail", "cognizable", THE System SHALL apply legal synonym expansion and section number guessing for retrieval
3. WHEN ranking search results, THE System SHALL use MMR (Maximal Marginal Relevance) with λ≈0.7 to balance relevance and diversity
4. WHEN re-ranking results, THE System SHALL apply weights of relevance 0.6, statute-edge boost 0.25, and recency 0.15
5. WHEN filtering results by temporal scope, THE System SHALL exclude statute chunks outside their effective date range and prefer judgments ≤ as-on date

### Requirement 4: Citation Verification and Hallucination Detection

**User Story:** As a legal professional, I want every factual claim to be backed by verifiable sources with exact quotes, so that I can trust the accuracy of the AI's responses.

#### Acceptance Criteria

1. WHEN the System generates an answer, THE System SHALL verify that each material claim is supported by retrieved source chunks
2. WHEN including citations, THE System SHALL provide verbatim quotes of ≤300 characters from the source text
3. WHEN a citation is referenced, THE System SHALL include the canonical ID and ensure it exists in the knowledge base
4. IF a claim cannot be verified against retrieved sources, THEN THE System SHALL flag the claim or remove it from the response
5. WHEN post-processing answers, THE System SHALL perform string matching to verify all quoted text matches source content exactly

### Requirement 5: Temporal Correctness and As-On Date Reasoning

**User Story:** As a lawyer, I want the system to provide legally accurate information as of a specific date, so that I can rely on the temporal correctness of legal advice.

#### Acceptance Criteria

1. WHEN processing a query, THE System SHALL determine the as-on date (default: current date) for temporal filtering
2. WHEN retrieving statute sections, THE System SHALL only include sections that were effective on the as-on date
3. WHEN retrieving case law, THE System SHALL prioritize judgments decided on or before the as-on date
4. WHEN displaying answers, THE System SHALL clearly indicate the as-on date used for the legal analysis
5. WHERE a user specifies a historical date, THE System SHALL adjust retrieval to reflect the law as it existed on that date

### Requirement 6: Performance and Latency Requirements

**User Story:** As a user, I want fast responses to legal queries, so that I can maintain efficient workflow without delays.

#### Acceptance Criteria

1. WHEN processing a typical legal query, THE System SHALL complete end-to-end processing within 3-6 seconds at 95th percentile
2. WHEN performing hybrid search retrieval, THE System SHALL complete the search within 800 milliseconds
3. WHEN generating embeddings for queries, THE System SHALL cache results for 1 hour to improve performance
4. WHEN accessing frequently queried legal documents, THE System SHALL maintain in-memory cache of core document embeddings
5. WHEN system load increases, THE System SHALL maintain response times through efficient caching and connection pooling

### Requirement 7: Legal Knowledge Base Construction and Indexing

**User Story:** As a system administrator, I want efficient ingestion and indexing of legal documents, so that the knowledge base remains current and searchable.

#### Acceptance Criteria

1. WHEN ingesting the BNS PDF, THE System SHALL extract text, create legal-aware chunks, generate embeddings, and store in the vector database
2. WHEN processing Supreme Court PDFs from 2020, THE System SHALL handle approximately 1,664 documents totaling 233 MB
3. WHEN creating embeddings, THE System SHALL use OpenAI text-embedding-3-large model to generate 1536-dimension vectors
4. WHEN storing chunks in the database, THE System SHALL create HNSW indexes with M=16, ef_construction=200 for efficient similarity search
5. WHEN building the knowledge base, THE System SHALL create separate collections for kb_statutes and kb_cases

### Requirement 8: Cross-Reference Graph and Legal Relationships

**User Story:** As a legal researcher, I want the system to understand relationships between statutes and cases, so that I can discover related legal authorities.

#### Acceptance Criteria

1. WHEN processing legal documents, THE System SHALL identify and store cross-references between statute sections
2. WHEN analyzing judgments, THE System SHALL extract and normalize statute references to create judgment-to-statute edges
3. WHEN detecting case citations, THE System SHALL create judgment-to-judgment relationships in the graph
4. WHEN storing relationships, THE System SHALL maintain an adjacency list with edge types and weights for re-ranking
5. WHEN retrieving results, THE System SHALL boost scores for documents connected through the cross-reference graph

### Requirement 9: Query Understanding and Legal Context Processing

**User Story:** As a user asking legal questions, I want the system to understand legal terminology and context, so that I get relevant answers even with informal queries.

#### Acceptance Criteria

1. WHEN receiving a user query, THE System SHALL detect temporal intent, offense keywords, and procedural terms
2. WHEN processing legal terminology, THE System SHALL expand synonyms for terms like "FIR", "cognizable", "non-bailable", "remand", "SLP"
3. WHEN analyzing queries about specific offenses, THE System SHALL generate section number guesses (e.g., "robbery" → BNS:Sec:147 guess)
4. WHEN constructing retrieval queries, THE System SHALL synthesize legal synonyms and related terms for comprehensive search
5. WHEN the query lacks sufficient legal context, THE System SHALL ask one clarifying question rather than speculating

### Requirement 10: Answer Generation with Legal Precision

**User Story:** As a legal professional, I want AI-generated answers that are precise, well-cited, and acknowledge limitations, so that I can rely on the information for legal work.

#### Acceptance Criteria

1. WHEN generating answers for factual queries, THE System SHALL use temperature 0.2 for deterministic, precise responses
2. WHEN constructing prompts, THE System SHALL include up to 4 statute chunks and 4 case chunks with source IDs and quote span markers
3. WHEN the LLM generates responses, THE System SHALL enforce that each material claim includes a source ID citation
4. WHEN coverage is insufficient for a complete answer, THE System SHALL ask one clarifying question or refuse with explanation
5. WHEN generating comparative analysis, THE System SHALL use temperature 0.5 while maintaining citation requirements

### Requirement 11: Context Assembly and Token Management

**User Story:** As a system architect, I want efficient context assembly that maximizes relevant information while respecting token limits, so that the system provides comprehensive answers.

#### Acceptance Criteria

1. WHEN assembling context for the LLM, THE System SHALL create separate STATUTE and CASE blocks with clear delineation
2. WHEN managing token limits, THE System SHALL reserve ≥25% of the model window for the generated answer
3. WHEN including retrieved chunks, THE System SHALL insert source IDs and quote span markers for citation tracking
4. WHEN context exceeds token limits, THE System SHALL prioritize highest-scoring chunks and truncate appropriately
5. WHEN multiple chunks from the same document are retrieved, THE System SHALL merge overlapping content to reduce redundancy

### Requirement 12: Error Handling and Graceful Degradation

**User Story:** As a user, I want the system to handle errors gracefully and provide clear feedback, so that I understand when information may be incomplete.

#### Acceptance Criteria

1. WHEN retrieval fails to find sufficient relevant sources, THE System SHALL inform the user and suggest refining the query
2. WHEN the OpenAI API is unavailable, THE System SHALL return cached responses for common queries if available
3. WHEN citation verification fails, THE System SHALL retry with expanded retrieval or return "insufficient sources" message
4. WHEN processing times exceed acceptable thresholds, THE System SHALL log performance issues and suggest system optimization
5. WHEN legal terminology is ambiguous, THE System SHALL list missing facts needed rather than making assumptions

### Requirement 13: Evaluation and Quality Assurance

**User Story:** As a system administrator, I want comprehensive evaluation metrics, so that I can ensure the system meets accuracy and performance standards.

#### Acceptance Criteria

1. WHEN evaluating statute retrieval, THE System SHALL achieve ≥95% Hit@3 accuracy for correct sections in top-3 contexts
2. WHEN evaluating case retrieval, THE System SHALL achieve ≥90% Hit@5 accuracy for controlling cases in top-5 results
3. WHEN validating citations, THE System SHALL achieve 100% correctness for URL presence and quote string matching
4. WHEN measuring performance, THE System SHALL maintain p95 latency ≤3-6 seconds end-to-end
5. WHEN conducting lawyer evaluation, THE System SHALL achieve ≥4/5 CSAT rating on a golden set of 150 legal queries

### Requirement 14: Caching and Performance Optimization

**User Story:** As a system architect, I want intelligent caching strategies, so that the system provides fast responses while minimizing API costs.

#### Acceptance Criteria

1. WHEN processing queries, THE System SHALL cache query embeddings using LRU eviction with 10-50k capacity
2. WHEN performing ANN searches, THE System SHALL cache top-k results for hot queries with 1-6 hour TTL
3. WHEN accessing core legal documents, THE System SHALL maintain permanent in-memory cache for Constitution and major acts
4. WHEN the knowledge base is updated, THE System SHALL implement cache invalidation for affected documents
5. WHEN optimizing costs, THE System SHALL batch embedding requests and reuse cached embeddings where possible

### Requirement 15: Security and Data Privacy

**User Story:** As a system administrator, I want robust security measures, so that the system protects sensitive legal information and maintains user privacy.

#### Acceptance Criteria

1. WHEN storing legal documents, THE System SHALL encrypt all data at rest using industry-standard encryption
2. WHEN processing user queries, THE System SHALL not log sensitive content to prevent data leakage
3. WHEN accessing external APIs, THE System SHALL use secure connections and proper authentication
4. WHEN maintaining audit logs, THE System SHALL log query IDs, document IDs, and performance metrics without exposing content
5. WHEN handling user data, THE System SHALL comply with data privacy regulations and implement zero-retention policies where required

### Requirement 16: Monitoring and Observability

**User Story:** As a system administrator, I want comprehensive monitoring and logging, so that I can maintain system health and optimize performance.

#### Acceptance Criteria

1. WHEN processing queries, THE System SHALL log query ID, retrieved document IDs, response time, and success status
2. WHEN errors occur, THE System SHALL log error messages, stack traces, and request context for debugging
3. WHEN tracking performance, THE System SHALL monitor vector search time, LLM API call time, and total response time
4. WHEN monitoring costs, THE System SHALL track OpenAI API token usage and provide cost alerts
5. WHEN system health changes, THE System SHALL provide alerts for high error rates, slow response times, or resource exhaustion

### Requirement 17: Scalability and Load Management

**User Story:** As a system architect, I want the system to handle increasing load efficiently, so that performance remains consistent as usage grows.

#### Acceptance Criteria

1. WHEN query volume increases, THE System SHALL maintain response times through horizontal scaling of processing components
2. WHEN database load increases, THE System SHALL use connection pooling and read replicas for query distribution
3. WHEN memory usage grows, THE System SHALL implement efficient cache eviction and memory management
4. WHEN processing large document batches, THE System SHALL support parallel processing and background job queuing
5. WHEN system resources are constrained, THE System SHALL implement graceful degradation and load shedding

### Requirement 18: Testing with 2020 Supreme Court Data

**User Story:** As a system developer, I want to test the system with a focused dataset, so that I can validate functionality before scaling to the full corpus.

#### Acceptance Criteria

1. WHEN conducting initial testing, THE System SHALL process only Supreme Court PDFs from 2020 (1,664 documents, 233 MB)
2. WHEN validating BNS processing, THE System SHALL successfully chunk and index the complete BNS Act (a2023-45.pdf)
3. WHEN testing retrieval accuracy, THE System SHALL demonstrate correct section identification for robbery, theft, and cheating queries
4. WHEN evaluating performance, THE System SHALL meet latency requirements with the 2020 dataset before expanding
5. WHEN verifying citations, THE System SHALL ensure all generated citations link to actual content in the 2020 test corpus

### Requirement 19: Legal Synonym and Terminology Handling

**User Story:** As a legal professional using varied terminology, I want the system to understand legal synonyms and related terms, so that I can find relevant information regardless of specific word choices.

#### Acceptance Criteria

1. WHEN processing queries with legal terms, THE System SHALL expand synonyms for "FIR", "cognizable", "non-bailable", "remand", "SLP", "anticipatory"
2. WHEN analyzing legal concepts, THE System SHALL recognize related terms like "locus", "obiter", "ratio", "per incuriam"
3. WHEN handling procedural terminology, THE System SHALL map terms across different stages: FIR, Arrest, Charge, Trial, Appeal, SLP
4. WHEN processing offense-related queries, THE System SHALL connect common terms to specific BNS sections
5. WHEN building search queries, THE System SHALL include legal synonyms in BM25 keyword search while maintaining semantic search precision

### Requirement 20: Update Pipeline and Maintenance

**User Story:** As a system administrator, I want automated update capabilities, so that the knowledge base remains current with new legal developments.

#### Acceptance Criteria

1. WHEN new Supreme Court judgments are available, THE System SHALL support weekly case synchronization using SHA256 hash comparison
2. WHEN BNS amendments or corrigenda are published, THE System SHALL update effective_to dates for superseded sections and add new versions
3. WHEN knowledge base updates occur, THE System SHALL re-embed only changed content to minimize processing costs
4. WHEN index maintenance is required, THE System SHALL support nightly incremental updates and quarterly full compaction
5. WHEN monitoring update operations, THE System SHALL log document counts, success rates, and any processing errors
