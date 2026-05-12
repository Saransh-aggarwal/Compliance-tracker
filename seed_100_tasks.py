import os
import random
from database import get_session, Task, TaskLog
from retrieval import build_collection, index_tasks
from dotenv import load_dotenv

load_dotenv()

companies = ["Acme Corp", "TechNova", "Global Industries", "Stark Enterprises"]
states = ["California", "New York", "Texas", "London"]
units = ["HQ", "Branch Office", "Manufacturing Plant", "R&D Center"]

topics = {
    "monthly": [
        "Payroll Tax Deposit", "Safety Inspection Report", "Access Log Review", 
        "Fire Extinguisher Check", "Server Patching Report", "GST Return Filing",
        "Employee Shift Log Review", "Waste Disposal Manifest", "Water Quality Test", "Customer Feedback Audit"
    ],
    "quarterly": [
        "Financial Earnings Report", "ISO 27001 Internal Audit", "Diversity & Inclusion Review",
        "Quarterly Income Tax Advance", "Lift and Escalator Maintenance", "IT Asset Inventory",
        "Board of Directors Meeting Minutes", "Supplier Risk Assessment", "Employee Training Compliance", "Cybersecurity Penetration Test"
    ],
    "6 months": [
        "Half-Yearly Environmental Impact Report", "Software License Audit", "Benefits Enrollment Review",
        "Emergency Evacuation Drill", "Data Privacy Impact Assessment", "Vendor Contract Renewals",
        "Physical Security Audit", "Performance Review Cycle", "Energy Efficiency Report", "Business Continuity Plan Test"
    ],
    "yearly": [
        "Annual Financial Audit", "GDPR Compliance Certification", "Workplace Safety Certification",
        "Tax Return Filing", "Employee Handbook Update", "Anti-Bribery Policy Acknowledgement",
        "Carbon Footprint Report", "Executive Compensation Review", "Insurance Policy Renewal", "IT Disaster Recovery Audit"
    ]
}

def generate_tasks():
    tasks = []
    # Generate ~100 tasks
    for track_type, task_list in topics.items():
        # 10 topics per track type
        # For monthly and quarterly, create 3 variants each = 60
        # For 6 months and yearly, create 2 variants each = 40
        # Total = 100 tasks
        num_variants = 3 if track_type in ["monthly", "quarterly"] else 2
        
        for base_task in task_list:
            for i in range(num_variants):
                company = random.choice(companies)
                state = random.choice(states)
                unit = random.choice(units)
                
                tasks.append({
                    "task_name": f"{base_task} - {company} {unit}",
                    "description": f"Ensure completion and proper filing of the {base_task.lower()} for {company} located in {state}.",
                    "due_date": f"2026/12/{random.randint(10, 28)}",
                    "company_name": company,
                    "unit_name": unit,
                    "state": state,
                    "help_text": f"Standard procedure for {base_task}. Refer to company compliance manual section {random.randint(1,9)}.",
                    "track_type": track_type
                })
    return tasks

def seed_db():
    session = get_session()
    
    # Delete existing logs to avoid foreign key constraints
    session.query(TaskLog).delete()
    # Delete existing tasks for a clean slate
    session.query(Task).delete()
    session.commit()
    
    tasks_data = generate_tasks()
    
    db_tasks = []
    for data in tasks_data:
        task = Task(**data)
        session.add(task)
        db_tasks.append(task)
        
    session.commit()
    print(f"Inserted {len(db_tasks)} tasks into PostgreSQL.")
    
    # Refresh to get IDs
    for t in db_tasks:
        session.refresh(t)
        
    task_dicts = [t.to_dict() for t in db_tasks]
    session.close()
    
    print("Indexing tasks in ChromaDB...")
    import chromadb
    client = chromadb.PersistentClient(path="./chroma_db")
    try:
        client.delete_collection("semantic_search")
        print("Deleted old vector collection.")
    except Exception as e:
        print("No existing collection to delete.")
        pass
        
    collection = build_collection()
    index_tasks(collection, task_dicts)
    print("Indexed successfully into ChromaDB!")

if __name__ == "__main__":
    seed_db()
