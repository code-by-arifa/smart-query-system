-- Atomically escalate stale pending queries and create their audit records.
-- Row locks with SKIP LOCKED make concurrent API instances safe: each query
-- can be claimed and transitioned by at most one invocation.
create or replace function public.escalate_stale_queries()
returns integer
language plpgsql
security invoker
set search_path = public
as $$
declare
  escalated_count integer;
begin
  with candidates as materialized (
    select q.query_id
    from public.queries as q
    where q.status = 'Pending'
      and q.created_at < now() - interval '24 hours'
    for update of q skip locked
  ), updated as (
    update public.queries as q
    set status = 'Escalated',
        escalated_to_role = 'HOD',
        updated_at = now()
    from candidates as c
    where q.query_id = c.query_id
      and q.status = 'Pending'
    returning q.query_id
  )
  insert into public.escalation_record (query_id, reason)
  select u.query_id, 'No response within 24 hours'
  from updated as u;

  get diagnostics escalated_count = row_count;
  return escalated_count;
end;
$$;

-- This RPC is intended for the backend service key, never a browser client.
revoke all on function public.escalate_stale_queries() from public;
revoke all on function public.escalate_stale_queries() from anon;
revoke all on function public.escalate_stale_queries() from authenticated;
grant execute on function public.escalate_stale_queries() to service_role;
