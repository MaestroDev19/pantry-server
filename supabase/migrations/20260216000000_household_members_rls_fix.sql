-- Fix infinite recursion in RLS for household_members.
-- Users may read their own membership row only (user_id = auth.uid()).

alter table public.household_members enable row level security;

-- Drop existing policies on household_members to remove any recursive policy
do $$
declare
  r record;
begin
  for r in (
    select policyname, tablename, schemaname
    from pg_policies
    where schemaname = 'public' and tablename = 'household_members'
  ) loop
    execute format('drop policy if exists %I on public.household_members', r.policyname);
  end loop;
end
$$;

-- Allow users to read their own household membership (no recursion)
create policy "household_members_select_own"
  on public.household_members
  for select
  using (user_id = auth.uid());
