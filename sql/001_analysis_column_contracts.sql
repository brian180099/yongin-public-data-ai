begin;

create table if not exists analytics.dataset_contract_versions (
  source_database text not null check (source_database in ('local', 'supabase')),
  dataset_id text not null,
  source_last_success_at timestamptz not null,
  source_run_id uuid not null,
  source_raw_sha256 char(64) not null,
  validated_at timestamptz not null default now(),
  validation_status text not null check (validation_status = 'validated'),
  primary key (source_database, dataset_id)
);

create table if not exists analytics.dataset_column_contracts (
  source_database text not null,
  dataset_id text not null,
  column_name text not null,
  kind text not null check (kind in ('date', 'group')),
  allowed_operations text[] not null,
  date_format text,
  group_values jsonb,
  primary key (source_database, dataset_id, column_name),
  foreign key (source_database, dataset_id)
    references analytics.dataset_contract_versions (source_database, dataset_id)
    on delete cascade
);

create table if not exists analytics.dataset_contract_attempts (
  attempt_id uuid primary key default gen_random_uuid(),
  source_database text not null check (source_database in ('local', 'supabase')),
  dataset_id text not null,
  attempted_at timestamptz not null default now(),
  outcome text not null check (outcome in ('validated', 'failed')),
  failure_reason text,
  source_run_id uuid,
  source_raw_sha256 char(64)
);

create index if not exists dataset_contract_attempts_recent_idx
  on analytics.dataset_contract_attempts (source_database, dataset_id, attempted_at desc);

create or replace view analytics.dataset_source_fingerprints as
select d.dataset_id, d.last_success_at,
       latest.run_id as source_run_id,
       coalesce(latest.raw_sha256, hashed.raw_sha256) as source_raw_sha256
from collector.datasets d
left join lateral (
  select run_id, raw_sha256
  from collector.collection_runs
  where dataset_id=d.dataset_id and status in ('success', 'no_change')
  order by finished_at desc nulls last limit 1
) latest on true
left join lateral (
  select raw_sha256
  from collector.collection_runs
  where dataset_id=d.dataset_id and status in ('success', 'no_change')
    and raw_sha256 is not null
  order by finished_at desc nulls last limit 1
) hashed on true;

grant usage on schema analytics to yongin_collector_writer;
grant select on analytics.current_dataset_records, analytics.dataset_source_fingerprints
  to yongin_collector_writer;
grant select, insert, update, delete on
  analytics.dataset_contract_versions,
  analytics.dataset_column_contracts,
  analytics.dataset_contract_attempts
  to yongin_collector_writer;
grant select on
  analytics.dataset_source_fingerprints,
  analytics.dataset_contract_versions,
  analytics.dataset_column_contracts
  to yongin_analysis_reader;

commit;
