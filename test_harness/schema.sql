-- create table if not exists runs (
--     id integer primary key autoincrement,
--     start timestamp,
--     end timestamp
-- );

create table if not exists test_instances(
    run_id integer not null,
    env text not null,
    id text not null,
    status text not null,
    run_result text default null,
    compare_result text default null,

    primary key (run_id, env, id)
    -- foreign key (run_id) references runs(id) on delete cascade
);