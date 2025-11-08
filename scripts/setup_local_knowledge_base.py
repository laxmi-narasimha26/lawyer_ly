#!/usr/bin/env python3
"""
Local Knowledge Base Setup Script
Creates a minimal but functional legal knowledge base for MVP demonstration
"""

import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict
import requests
from datetime import datetime

# Sample Indian Legal Documents for MVP
SAMPLE_DOCUMENTS = {
    "constitution_fundamental_rights.txt": """
PART III - FUNDAMENTAL RIGHTS

Article 14 - Equality before law
The State shall not deny to any person equality before the law or the equal protection of the laws within the territory of India.

Article 19 - Protection of certain rights regarding freedom of speech, etc.
(1) All citizens shall have the right—
(a) to freedom of speech and expression;
(b) to assemble peaceably and without arms;
(c) to form associations or unions;
(d) to move freely throughout the territory of India;
(e) to reside and settle in any part of the territory of India; and
(f) to practise any profession, or to carry on any occupation, trade or business.

Article 21 - Protection of life and personal liberty
No person shall be deprived of his life or personal liberty except according to procedure established by law.

Article 32 - Right to Constitutional remedies
(1) The right to move the Supreme Court by appropriate proceedings for the enforcement of the rights conferred in this Part is guaranteed.
(2) The Supreme Court shall have power to issue writs, including writs in the nature of habeas corpus, mandamus, prohibition, certiorari and quo-warranto, whichever may be appropriate, for the enforcement of any of the rights conferred in this Part.
""",

    "contract_act_essentials.txt": """
INDIAN CONTRACT ACT, 1872

Section 10 - What agreements are contracts
All agreements are contracts if they are made by the free consent of parties competent to contract, for a lawful consideration and with a lawful object, and are not hereby expressly declared to be void.

Essential Elements of a Valid Contract:
1. Offer and Acceptance (Sections 3-9)
2. Consideration (Sections 23-25)
3. Capacity of Parties (Sections 11-12)
4. Free Consent (Sections 13-22)
5. Lawful Object (Section 23)
6. Legal Formalities (Section 10)

Section 2(h) - Contract defined
An agreement enforceable by law is a contract.

Section 2(e) - Agreement defined
Every promise and every set of promises, forming the consideration for each other, is an agreement.

Section 23 - What consideration and objects are lawful, and what not
The consideration or object of an agreement is lawful, unless—
it is forbidden by law; or
is of such a nature that, if permitted, it would defeat the provisions of any law; or
is fraudulent; or
involves or implies injury to the person or property of another; or
the Court regards it as immoral, or opposed to public policy.
""",

    "ipc_major_sections.txt": """
INDIAN PENAL CODE, 1860

Chapter IV - General Exceptions

Section 76 - Act done by a person bound, or by mistake of fact believing himself bound, by law
Nothing is an offence which is done by a person who is, or who by reason of a mistake of fact and not by reason of a mistake of law in good faith believes himself to be, bound by law to do it.

Section 79 - Act done by a person justified, or by mistake of fact believing himself justified, by law
Nothing is an offence which is done by any person who is justified by law, or who by reason of a mistake of fact and not by reason of a mistake of law in good faith, believes himself to be justified by law in doing it.

Chapter XVI - Of Offences Affecting the Human Body

Section 299 - Culpable homicide
Whoever causes death by doing an act with the intention of causing death, or with the intention of causing such bodily injury as is likely to cause death, or with the knowledge that he is likely by such act to cause death, commits the offence of culpable homicide.

Section 300 - Murder
Except in the cases hereinafter excepted, culpable homicide is murder, if the act by which the death is caused is done with the intention of causing death, or—
Secondly.—If it is done with the intention of causing such bodily injury as the offender knows to be likely to cause the death of the person to whom the harm is caused, or—
Thirdly.—If it is done with the intention of causing bodily injury to any person and the bodily injury intended to be inflicted is sufficient in the ordinary course of nature to cause death, or—
Fourthly.—If the person committing the act knows that it is so imminently dangerous that it must, in all probability, cause death or such bodily injury as is likely to cause death, and commits such act without any excuse for incurring the risk of causing death or such injury as aforesaid.
""",

    "landmark_cases.txt": """
LANDMARK SUPREME COURT CASES

Kesavananda Bharati v. State of Kerala (1973)
Citation: AIR 1973 SC 1461
Key Principle: Basic Structure Doctrine
The Supreme Court held that Parliament cannot amend the Constitution so as to destroy its basic structure. The basic features of the Constitution cannot be altered by constitutional amendments.

Maneka Gandhi v. Union of India (1978)
Citation: AIR 1978 SC 597
Key Principle: Expanded interpretation of Article 21
The Court expanded the scope of Article 21 (right to life and personal liberty) to include the right to live with human dignity and various other rights flowing from it.

Vishaka v. State of Rajasthan (1997)
Citation: AIR 1997 SC 3011
Key Principle: Sexual harassment at workplace
The Court laid down guidelines for prevention of sexual harassment of women at workplace, which were later codified in the Sexual Harassment of Women at Workplace Act, 2013.

Balfour v. Balfour (1919) 2 KB 571
Key Principle: Domestic agreements and intention to create legal relations
Agreements between husband and wife made in the ordinary course of their life together are not contracts because there is no intention to create legal relations.

Carlill v. Carbolic Smoke Ball Co. (1893) 1 QB 256
Key Principle: Unilateral contracts and consideration
A unilateral offer made to the world at large can be accepted by anyone who performs the conditions stated in the offer. Performance of the condition constitutes both acceptance and consideration.
""",

    "legal_procedures.txt": """
CIVIL PROCEDURE CODE, 1908

Order VII - Plaint

Rule 1 - Contents of plaint
Every plaint shall contain the following particulars:—
(a) the name of the Court in which the suit is brought;
(b) the name, description and place of residence of the plaintiff;
(c) the name, description and place of residence of the defendant, so far as they can be ascertained;
(d) where the plaintiff or the defendant is a minor or person of unsound mind, a statement to that effect;
(e) the facts constituting the cause of action and when it arose;
(f) that the Court has jurisdiction to try the suit;
(g) that the suit is not barred by any law;
(h) the relief which the plaintiff claims;
(i) where the plaintiff has allowed a set-off or relinquished a portion of his claim, the amount so allowed or relinquished; and
(j) the value of the subject-matter of the suit for the purposes of jurisdiction and of court-fees, so far as the case admits.

LIMITATION ACT, 1963

Section 3 - Bar of limitation
Subject to the provisions contained in sections 4 to 24 (inclusive), every suit instituted, appeal preferred, and application made after the prescribed period shall be dismissed, although limitation has not been set up as a defence.

Article 113 - Suit for compensation for acts not otherwise specifically provided for - 3 years from when the right to sue accrues.

Article 137 - Any other suit not otherwise specifically provided for - 3 years from when the right to sue accrues.
"""
}

class LocalKnowledgeBaseSetup:
    def __init__(self, knowledge_base_path: str = "./data/knowledge_base"):
        self.kb_path = Path(knowledge_base_path)
        self.kb_path.mkdir(parents=True, exist_ok=True)
        
    def create_sample_documents(self):
        """Create sample legal documents for the knowledge base"""
        print("Creating sample legal documents...")
        
        for filename, content in SAMPLE_DOCUMENTS.items():
            file_path = self.kb_path / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ Created {filename}")
    
    def create_metadata_index(self):
        """Create metadata index for the documents"""
        print("Creating metadata index...")
        
        metadata = {
            "created_at": datetime.now().isoformat(),
            "documents": [],
            "total_documents": len(SAMPLE_DOCUMENTS),
            "version": "1.0.0"
        }
        
        for filename in SAMPLE_DOCUMENTS.keys():
            doc_metadata = {
                "filename": filename,
                "title": filename.replace('_', ' ').replace('.txt', '').title(),
                "type": self._get_document_type(filename),
                "size": len(SAMPLE_DOCUMENTS[filename]),
                "created_at": datetime.now().isoformat(),
                "indexed": False
            }
            metadata["documents"].append(doc_metadata)
        
        metadata_path = self.kb_path / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✓ Created metadata index with {len(SAMPLE_DOCUMENTS)} documents")
    
    def _get_document_type(self, filename: str) -> str:
        """Determine document type based on filename"""
        if 'constitution' in filename:
            return 'constitutional_law'
        elif 'contract' in filename:
            return 'contract_law'
        elif 'ipc' in filename:
            return 'criminal_law'
        elif 'cases' in filename:
            return 'case_law'
        elif 'procedure' in filename:
            return 'procedural_law'
        else:
            return 'general'
    
    def create_sample_queries(self):
        """Create sample queries for testing"""
        print("Creating sample queries...")
        
        sample_queries = [
            {
                "query": "What are the essential elements of a valid contract?",
                "expected_sources": ["contract_act_essentials.txt"],
                "category": "contract_law"
            },
            {
                "query": "What is Article 21 of the Constitution?",
                "expected_sources": ["constitution_fundamental_rights.txt"],
                "category": "constitutional_law"
            },
            {
                "query": "What is the difference between murder and culpable homicide?",
                "expected_sources": ["ipc_major_sections.txt"],
                "category": "criminal_law"
            },
            {
                "query": "What is the basic structure doctrine?",
                "expected_sources": ["landmark_cases.txt"],
                "category": "constitutional_law"
            },
            {
                "query": "What is the limitation period for filing a suit?",
                "expected_sources": ["legal_procedures.txt"],
                "category": "procedural_law"
            }
        ]
        
        queries_path = self.kb_path / "sample_queries.json"
        with open(queries_path, 'w', encoding='utf-8') as f:
            json.dump(sample_queries, f, indent=2)
        
        print(f"✓ Created {len(sample_queries)} sample queries")
    
    def setup(self):
        """Run the complete setup process"""
        print("Setting up local knowledge base for MVP...")
        print("=" * 50)
        
        self.create_sample_documents()
        self.create_metadata_index()
        self.create_sample_queries()
        
        print("=" * 50)
        print("✅ Local knowledge base setup complete!")
        print(f"📁 Knowledge base location: {self.kb_path.absolute()}")
        print(f"📊 Total documents: {len(SAMPLE_DOCUMENTS)}")
        print("\nNext steps:")
        print("1. Start the local services: docker-compose -f docker-compose.local.yml up -d")
        print("2. Run the ingestion script: python scripts/ingest_local_documents.py")
        print("3. Start the backend: python backend/main.py")
        print("4. Start the frontend: cd frontend && npm run dev")

if __name__ == "__main__":
    setup = LocalKnowledgeBaseSetup()
    setup.setup()