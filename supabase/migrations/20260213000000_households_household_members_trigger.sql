-- Reference migration: households, household_members, and trigger to add owner as member on personal household insert.
-- Apply in Supabase Dashboard or via supabase db push if using local Supabase CLI.
-- Tables may already exist; trigger function uses CREATE OR REPLACE for idempotency.

-- Table: public.households
create table if not exists public.households (
  id uuid not null default gen_random_uuid(),
  name text not null,
  invite_code text not null,
  created_at timestamp with time zone null default now(),
  is_personal boolean not null default false,
  owner_id uuid null,
  constraint households_pkey primary key (id),
  constraint households_invite_code_key unique (invite_code),
  constraint households_owner_id_fkey foreign key (owner_id) references auth.users (id)
) tablespace pg_default;

-- Table: public.household_members
create table if not exists public.household_members (
  id uuid not null default gen_random_uuid(),
  household_id uuid null,
  user_id uuid null,
  joined_at timestamp with time zone null default now(),
  constraint household_members_pkey primary key (id),
  constraint household_members_user_id_key unique (user_id),
  constraint household_members_household_id_fkey foreign key (household_id) references public.households (id) on delete cascade,
  constraint household_members_user_id_fkey foreign key (user_id) references auth.users (id) on delete cascade
) tablespace pg_default;

create index if not exists idx_household_members_user on public.household_members using btree (user_id) tablespace pg_default;
create index if not exists idx_household_members_household on public.household_members using btree (household_id) tablespace pg_default;
create index if not exists idx_household_members_household_user on public.household_members using btree (household_id, user_id) tablespace pg_default;

-- Function: add owner as household_member when a personal household is inserted
create or replace function public.household_after_insert_member_trigger()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.is_personal and new.owner_id is not null then
    insert into public.household_members (household_id, user_id, joined_at)
    values (new.id, new.owner_id, now());
  end if;
  return new;
end;
$$;

-- Trigger: run after insert on households
drop trigger if exists household_insert_member_trigger on public.households;
create trigger household_insert_member_trigger
  after insert on public.households
  for each row
  execute function public.household_after_insert_member_trigger();
