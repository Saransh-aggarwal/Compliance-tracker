import os
from sqlalchemy import create_engine, Column, Integer, String, text, DateTime, ForeignKey, Boolean
from datetime import datetime
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    due_date = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    unit_name = Column(String, nullable=False)
    state = Column(String, nullable=False)
    help_text = Column(String, nullable=False)
    track_type = Column(String, nullable=False, default='yearly')

    def to_dict(self):
        return {
            "id": self.id,
            "task_name": self.task_name,
            "description": self.description,
            "due_date": self.due_date,
            "company_name": self.company_name,
            "unit_name": self.unit_name,
            "state": self.state,
            "help_text": self.help_text,
            "track_type": self.track_type
        }

class TaskLog(Base):
    __tablename__ = 'task_logs'

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    execution_date = Column(DateTime, default=datetime.utcnow)
    period_label = Column(String, nullable=False)
    status = Column(String, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "execution_date": self.execution_date.strftime("%Y-%m-%d %H:%M:%S") if self.execution_date else None,
            "period_label": self.period_label,
            "status": self.status
        }

class EmailAccount(Base):
    __tablename__ = 'email_accounts'

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    app_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    last_sync_time = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "app_password": self.app_password,
            "is_active": self.is_active,
            "last_sync_time": self.last_sync_time.strftime("%Y-%m-%d %H:%M:%S") if self.last_sync_time else None
        }

class AdminUser(Base):
    __tablename__ = 'admin_users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False) # In a real app, use hashed passwords
    security_question = Column(String, nullable=True)
    security_answer = Column(String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username
        }

def get_engine():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set in environment variables.")
    return create_engine(database_url)

def get_session():
    engine = get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

def init_db():
    engine = get_engine()
    with engine.connect() as conn:
        try:
            print(conn.execute(text("SELECT current_user, current_database()")).fetchone())
        except Exception:
            print("Running database initialization...")
    Base.metadata.create_all(bind=engine)
    create_default_admin()

def create_default_admin():
    session = get_session()
    admin = session.query(AdminUser).filter(AdminUser.username == "admin").first()
    if not admin:
        admin = AdminUser(username="admin", password="password123", security_question="What is your favorite color?", security_answer="blue")
        session.add(admin)
        session.commit()
    session.close()

def authenticate_admin(username, password):
    session = get_session()
    admin = session.query(AdminUser).filter(AdminUser.username == username, AdminUser.password == password).first()
    session.close()
    return admin is not None

def register_admin(username, password, security_question, security_answer):
    session = get_session()
    existing = session.query(AdminUser).filter(AdminUser.username == username).first()
    if existing:
        session.close()
        return False, "Username already exists."
    
    new_admin = AdminUser(username=username, password=password, security_question=security_question, security_answer=security_answer.lower())
    session.add(new_admin)
    session.commit()
    session.close()
    return True, "Registration successful."

def get_security_question(username):
    session = get_session()
    admin = session.query(AdminUser).filter(AdminUser.username == username).first()
    question = admin.security_question if admin else None
    session.close()
    return question

def reset_password(username, security_answer, new_password):
    session = get_session()
    admin = session.query(AdminUser).filter(AdminUser.username == username).first()
    if not admin:
        session.close()
        return False, "User not found."
    
    if admin.security_answer and admin.security_answer.lower() == security_answer.lower():
        admin.password = new_password
        session.commit()
        session.close()
        return True, "Password reset successfully."
    else:
        session.close()
        return False, "Incorrect security answer."

def get_all_tasks():
    session = get_session()
    tasks = session.query(Task).all()
    result = [t.to_dict() for t in tasks]
    session.close()
    return result

def get_task_by_id(task_id):
    session = get_session()
    task = session.query(Task).filter(Task.id == task_id).first()
    result = task.to_dict() if task else None
    session.close()
    return result

def check_task_duplicate(task_id, period_label):
    session = get_session()
    log = session.query(TaskLog).filter(TaskLog.task_id == task_id, TaskLog.period_label == period_label).first()
    result = log.to_dict() if log else None
    session.close()
    return result

def add_task_log(task_id, period_label, status):
    session = get_session()
    log = TaskLog(task_id=task_id, period_label=period_label, status=status)
    session.add(log)
    session.commit()
    session.refresh(log)
    result = log.to_dict()
    session.close()
    return result

def get_task_logs_for_year(year: str):
    session = get_session()
    logs = session.query(TaskLog).filter(TaskLog.period_label.like(f"{year}%")).all()
    result = [log.to_dict() for log in logs]
    session.close()
    return result

def add_task(task_data):
    session = get_session()
    task = Task(**task_data)
    session.add(task)
    session.commit()
    session.refresh(task)
    result = task.to_dict()
    session.close()
    return result

def add_email_account(email, app_password):
    session = get_session()
    # Check if exists
    existing = session.query(EmailAccount).filter(EmailAccount.email == email).first()
    if existing:
        existing.app_password = app_password
        existing.is_active = True
        session.commit()
        session.refresh(existing)
        result = existing.to_dict()
    else:
        account = EmailAccount(email=email, app_password=app_password)
        session.add(account)
        session.commit()
        session.refresh(account)
        result = account.to_dict()
    session.close()
    return result

def get_all_email_accounts():
    session = get_session()
    accounts = session.query(EmailAccount).all()
    result = [a.to_dict() for a in accounts]
    session.close()
    return result

def delete_email_account(account_id):
    session = get_session()
    account = session.query(EmailAccount).filter(EmailAccount.id == account_id).first()
    if account:
        session.delete(account)
        session.commit()
        success = True
    else:
        success = False
    session.close()
    return success

def update_last_sync_time(account_id, sync_time=None):
    if sync_time is None:
        sync_time = datetime.utcnow()
    session = get_session()
    account = session.query(EmailAccount).filter(EmailAccount.id == account_id).first()
    if account:
        account.last_sync_time = sync_time
        session.commit()
    session.close()
