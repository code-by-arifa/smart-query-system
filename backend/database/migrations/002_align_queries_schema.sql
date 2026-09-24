-- Keeps a new or restored Supabase database aligned with fields already used
-- by the API. All added columns are nullable so existing queries remain valid.
alter table queries
  add column if not exists assigned_role varchar(50),
  add column if not exists escalated_to_role varchar(50),
  add column if not exists hod_comment text;

-- PostgreSQL normally names the inline constraint in schema.sql
-- "queries_status_check". Confirm its name in Supabase before running the next
-- two statements if your database was created differently.
alter table queries drop constraint if exists queries_status_check;
alter table queries add constraint queries_status_check check (status in (
  'Pending',
  'In Progress',
  'Resolved',
  'Escalated',
  'Reassigned by HOD'
));

create index if not exists idx_queries_assigned_role on queries(assigned_role);
create index if not exists idx_queries_escalated_to_role on queries(escalated_to_role);
