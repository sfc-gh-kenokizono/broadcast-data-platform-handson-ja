# 実装共通仕様

本教材は旧 broadcast-viewing-handson-ja を参考にした別教材。旧フォルダと復元バックアップは保持する。2026-09-15にトライアル実機検証を実施し、その後ユーザーの明示依頼で旧トライアルDB・専用WH・API統合・ロールを削除した。実機の実施範囲はdocs/verification.mdを参照。

## Names
- Database BCAST_PLATFORM_HANDSON
- Schemas RAW, NW01, NW02, NW03, NW04, NW05, COMMON, ML, MART, INTEGRATIONS
- Warehouses BCAST_PLATFORM_NW01_WH through NW05_WH, BCAST_PLATFORM_COMMON_WH
- Roles BCAST_PLATFORM_ENGINEER_ROLE, BCAST_PLATFORM_ANALYST_ROLE
- Git integration BCAST_PLATFORM_GIT_API, repository INTEGRATIONS.BCAST_PLATFORM_REPO
- Repository sfc-gh-kenokizono/broadcast-data-platform-handson-ja (private)

## Data contract
- RAW.VIEWING_LOG_NW01 through NW05: EVENT_ID VARCHAR, NETWORK_ID VARCHAR, DEVICE_ID VARCHAR, VIEW_FROM TIMESTAMP_NTZ, VIEW_TO TIMESTAMP_NTZ, GENRE VARCHAR.
- Input data/viewing_log_nw01.parquet through nw05.parquet. Parquet internal ZSTD compression. Deterministic synthetic 30-day data, 2026-07-01 through 2026-07-30. Shared 200 device IDs D0001..D0200. No overlapping viewing intervals for a device across stations. Uppercase station IDs, lowercase/fullwidth variants in GENRE and surrounding spaces for simple cleansing.
- Genres after cleaning: NEWS, DRAMA, VARIETY, ANIME, SPORTS. Explicitly map fullwidth variants rather than claim general Unicode normalization.
- RAW.DEVICE_LABELS: DEVICE_ID VARCHAR, LABEL_AVAILABLE BOOLEAN, TARGET_SPORTS_FAN INTEGER. data/device_labels.parquet. Synthetic educational binary sports-interest label, NOT demographics or a real person attribute. Non-panel target is NULL; labels available on fixed 100 of 200 devices. Both classes in training/evaluation; generate viewing habits with noisy relationship to target. Do not put target/label availability in model features.
- NWxx.CLEAN_VIEWING: same raw columns, plus VIEW_MINUTES FLOAT. One event per row, EVENT_ID unique within station. Test input remains all valid after cleansing; defects can be demonstrated via read-only test fixtures.
- NWxx.MART_DEVICE_DAILY: NETWORK_ID VARCHAR, DEVICE_ID VARCHAR, VIEW_DATE DATE, GENRE VARCHAR, SESSION_COUNT INTEGER, VIEW_MINUTES FLOAT. Grain station/device/day/genre. Materialized table.
- COMMON.VIEWING_DAILY: same columns as station mart. Materialized UNION ALL of 5 marts, no deduplication.
- ML.PREDICTIONS: DEVICE_ID VARCHAR, PREDICTED_SPORTS_FAN INTEGER, MODEL_NAME VARCHAR, MODEL_VERSION VARCHAR, PREDICTED_AT TIMESTAMP_NTZ. One device per row. Notebook writes this only after model registration/inference. No true labels exposed to downstream app.
- ML registered model SPORTS_INTEREST_MODEL, explicit version V1 initially. Existing version: stop and request a new explicit version; never delete or silently reuse. PREDICTED_AT records UTC save time as TIMESTAMP_NTZ.
- MART.SV_VIEWING: semantic view over COMMON.VIEWING_DAILY only, independent of optional Search and ML output.
- MART.VIEWING_AGENT: Analyst-only agent using SV_VIEWING, common warehouse.

## Flow and scope
Required: setup/load, 5 station dbt cleansing+tests+materialized marts, final common union, one MLOps notebook, Streamlit, SQL semantic view, GUI Agent -> CoWork.
Per station runs must actually use their own warehouse (including tests); choose explicit dbt targets and selectors to avoid reliance on implicit per-model behavior. Common build only after all 5 station runs passed. dbt views may defer compute so use materialized clean tables and marts for clear attribution.
Supplemental: basic SQL, Search, scheduling, detailed operations. Instructor-only App Runtime; no App Runtime project here. No DCR, pickle, participant CoCo Desktop requirement. Main path must succeed without supplements.

## Files / ownership
- data agent: scripts/, data/, sql/01_setup.sql, sql/02_load_parquet.sql, sql/cleanup.sql, requirements-dev.txt, docs/01_setup.md
- dbt agent: dbt/, docs/02_dbt.md (no other files)
- ML agent: notebooks/03_mlops.ipynb, docs/03_mlops.md (dedicated notebook tools only)
- app/AI agent: app/, sql/04_semantic.sql, sql/05_agent.sql, docs/04_streamlit.md, docs/05_agent.md, docs/agent_texts.md
- main: README.md, CONTRACT.md, verification scripts/docs, supplemental/, .gitignore

## Safety and verification
Cloud execution must target the explicitly authorized trial, not the session's internal Snowhouse connection. Dedicated notebook tools for notebooks; do not execute untrusted pickle. Shared output columns must follow this contract. SQL identifiers fully qualified where appropriate. SQL scripts must not alter users' default roles or default warehouses. New cleanup remains limited to new-project resources; the old-trial removal was a separate explicitly authorized operation. Do not claim GUI fallback equivalence until actually tested.