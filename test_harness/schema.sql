create table if not exists runs (
    id integer primary key autoincrement, -- can be obtained in python via cursor.lastrowid on INSERT
    start timestamp, -- tests for this run cannot run before `start`
    end timestamp default null -- when run finished
);

create table if not exists test_instances(
    run_id integer not null,
    env text not null, -- baseline, target
    id text not null,
    status text not null, -- queued, waiting, running, complete
    run_result text default null, -- PASS, FAIL
    compare_result text default null, -- PASS, FAIL

    primary key (run_id, env, id)
    -- foreign key (run_id) references runs(id) on delete cascade
);