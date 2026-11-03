-- Lit Crit site accounts: one row of saved progress per user.
-- Paste this whole file into Supabase > SQL Editor > New query, then click Run. Safe to run again.

create table if not exists public.progress (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  data       jsonb not null default '{}'::jsonb,   -- {answers, scored, scores}, as the site keeps them
  updated_at timestamptz not null default now()
);

-- Each signed-in visitor can see and change only their own row.
alter table public.progress enable row level security;

drop policy if exists "read own progress" on public.progress;
create policy "read own progress" on public.progress
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "add own progress" on public.progress;
create policy "add own progress" on public.progress
  for insert to authenticated with check ((select auth.uid()) = user_id);

drop policy if exists "update own progress" on public.progress;
create policy "update own progress" on public.progress
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

grant select, insert, update on public.progress to authenticated;
revoke all on public.progress from anon;

-- Keep-awake ping (called twice a week by .github/workflows/keepalive.yml).
create or replace function public.keepalive()
returns timestamptz language sql stable security invoker set search_path = '' as $$ select now() $$;
revoke all on function public.keepalive() from public;
grant execute on function public.keepalive() to anon, authenticated;
