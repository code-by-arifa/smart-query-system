-- Run this once in the Supabase SQL editor before starting the upgraded API.
alter table users add column if not exists is_active boolean not null default true;

alter table queries add column if not exists assigned_to uuid references users(user_id);
alter table queries add column if not exists priority varchar(10) not null default 'Medium'
  check (priority in ('Low', 'Medium', 'High'));
alter table queries add column if not exists student_name varchar(150);
alter table queries add column if not exists gmail_message_id varchar(255) unique;
alter table queries add column if not exists gmail_thread_id varchar(255);
alter table queries add column if not exists source varchar(30) not null default 'manual';
alter table queries add column if not exists updated_at timestamp default now();
alter table queries add column if not exists resolved_at timestamp;

create table if not exists query_attachments (
  attachment_id uuid primary key default gen_random_uuid(),
  query_id uuid not null references queries(query_id) on delete cascade,
  file_name varchar(255) not null,
  mime_type varchar(150),
  storage_path text not null,
  size_bytes integer
);

create index if not exists idx_queries_assigned_to on queries(assigned_to);
create index if not exists idx_queries_dept_status on queries(dept_id, status);
create index if not exists idx_activity_log_timestamp on activity_log(timestamp desc);
