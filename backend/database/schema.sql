-- Departments
create table departments (
  dept_id uuid primary key default gen_random_uuid(),
  dept_name varchar(100) not null,
  contact_email varchar(150) unique
);

-- Users (staff, not students — students never log in)
create table users (
  user_id uuid primary key default gen_random_uuid(),
  dept_id uuid references departments(dept_id),
  name varchar(100) not null,
  email varchar(150) unique not null,
  role varchar(50) not null check (role in ('Admin','Instructor','HOD','Department')),
  created_at timestamp default now()
);

-- Queries
create table queries (
  query_id uuid primary key default gen_random_uuid(),
  dept_id uuid references departments(dept_id),
  student_email varchar(150) not null,
  subject varchar(255) not null,
  query_text text not null,
  category varchar(50),
  status varchar(30) not null default 'Pending'
    check (status in ('Pending','In Progress','Resolved','Escalated')),
  created_at timestamp default now()
);

-- AI classification results
create table ai_classification_log (
  log_id uuid primary key default gen_random_uuid(),
  query_id uuid references queries(query_id) on delete cascade,
  predicted_category varchar(50) not null,
  confidence_score decimal(5,2),
  classification_time timestamp default now()
);

-- Reply drafts / sent replies
create table reply_history (
  reply_id uuid primary key default gen_random_uuid(),
  query_id uuid references queries(query_id) on delete cascade,
  generated_reply text not null,
  approved_by uuid references users(user_id),
  sent_time timestamp
);

-- Escalations
create table escalation_record (
  escalation_id uuid primary key default gen_random_uuid(),
  query_id uuid references queries(query_id) on delete cascade,
  escalated_to uuid references users(user_id),
  escalation_time timestamp not null default now(),
  reason text
);

-- Activity log (audit trail)
create table activity_log (
  activity_id uuid primary key default gen_random_uuid(),
  user_id uuid references users(user_id),
  action text not null,
  timestamp timestamp default now()
);

-- Indexes mentioned in the SDD (5.3)
create index idx_queries_status on queries(status);
create index idx_queries_category on queries(category);