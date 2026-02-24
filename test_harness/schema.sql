-- a "run" represents a set of tests being run on both environments.
-- a run can be scheduled to start running in the future.
create table if not exists runs (
    id integer primary key autoincrement, -- can be obtained in python via cursor.lastrowid on INSERT
    start timestamp, -- tests for this run cannot run before `start`
    end timestamp default null -- when run finished
);

-- a test_instance represents a single tool running in an environment.
-- the test's processing status is tracked through a few states (below),
-- and the result of both the tool execution (did it execute without crashing?)
-- and data equivalence (did same inputs produce same outputs?) will determine
-- the overall "passing" status.
-- we expect all "baseline" test_instances to pass execution. when comparing
-- the output of each environment, the compare_result for both (run_id, id)
-- rows should be set to the same value (ie both PASS or both FAIL).
create table if not exists test_instances(
    run_id integer not null,
    env text not null, -- baseline, target
    id text not null,
    status text not null, -- queued, waiting, running, complete TODO: comparing?
    run_result text default null, -- PASS, FAIL
    compare_result text default null, -- PASS, FAIL

    primary key (run_id, env, id)
    -- foreign key (run_id) references runs(id) on delete cascade
);

-- Get complete test_instances pass/fail status per tool.
create view if not exists complete_tests_passing as 
    -- cannot use run_passed and compare_passed within SELECT
    -- so put that into a CTE.
    with complete_tests as (
        select
            run_id, 
            id, 
            cast(min(ifnull(run_result, 0)=='PASS') as boolean) as run_passed, 
            cast(min(ifnull(compare_result, 0)=='PASS') as boolean) as compare_passed 
        from 
            test_instances
        where
            status='complete'
        group by 
            run_id, id)
    select 
        run_id, 
        id, 
        run_passed, 
        compare_passed, 
        cast(min(run_passed, compare_passed) as boolean) as both_passed
    from complete_tests;

