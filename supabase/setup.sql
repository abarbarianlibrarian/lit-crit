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

-- "Flag an error" reports (written only by the `flag` Edge Function in supabase/functions/flag).
create table if not exists public.flags (
  id bigint generated always as identity primary key, created_at timestamptz not null default now(),
  category text not null, message text not null, item text, item_id text, page_url text, email text, name text,
  user_id uuid references auth.users (id) on delete set null, ip_hash text, forwarded boolean not null default false
);
create index if not exists flags_ip_time on public.flags (ip_hash, created_at);
alter table public.flags enable row level security;
revoke all on public.flags from anon, authenticated;
-- Private settings for Edge Functions: airtable_flag_webhook (the Airtable automation's webhook URL) and ip_salt.
create table if not exists public.app_config (key text primary key, value text not null);
alter table public.app_config enable row level security;
revoke all on public.app_config from anon, authenticated;

-- Profiles: student or coach, graduation year (students), school (school_id = Schools Master record
-- in the Master Tab Room base, empty for a school typed in by hand).
create table if not exists public.profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  role text check (role in ('student', 'coach')),
  graduation_year smallint check (graduation_year between 2000 and 2100),
  school text check (char_length(school) <= 120),
  school_id text check (school_id ~ '^rec[A-Za-z0-9]{14}$'),
  updated_at timestamptz not null default now(),
  constraint coach_has_no_grad_year check (role is distinct from 'coach' or graduation_year is null)
);
alter table public.profiles enable row level security;
drop policy if exists "read own profile" on public.profiles;
create policy "read own profile" on public.profiles for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists "add own profile" on public.profiles;
create policy "add own profile" on public.profiles for insert to authenticated with check ((select auth.uid()) = user_id);
drop policy if exists "update own profile" on public.profiles;
create policy "update own profile" on public.profiles for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
grant select, insert, update on public.profiles to authenticated;
revoke all on public.profiles from anon;
