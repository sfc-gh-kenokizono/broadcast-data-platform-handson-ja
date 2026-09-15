-- ============================================
-- 任意: この新教材のDB内データ・モデル・公開済みアプリ等と専用リソースを削除する。
-- 自動実行禁止。必要な成果物を退避し、削除対象を確認してから実行する。
-- 先に各自のNotebookでConnectedからサービスをSuspendし、SUSPENDEDを確認する。
-- 教材DB削除やブラウザー終了だけでは個人用Notebookサービスは停止しない。
-- 同名の環境を他の参加者と共有している場合は実行しない。
-- 実行前に、各利用者がWorkspace側の私用開発アプリを別途停止し、
-- 不要になったこの教材専用のアプリ／ソースを削除する。他用途のWorkspaceは削除しない。
-- DB内の公開済みStreamlit削除だけで、Workspaceや開発アプリの停止・削除は完了しない。
-- Workspace側の残存・稼働状態も別途確認する。詳しくはdocs/01_setup.mdの後片付けを参照。
-- このSQLはcompute poolを削除・停止しない。共有・既定・システム管理poolは対象外。
-- 別途用意した教材専用poolのみ、管理者が他の利用がないことを確認し別手順で片付ける。
-- ============================================
USE ROLE ACCOUNTADMIN;

DROP DATABASE IF EXISTS BCAST_PLATFORM_HANDSON;
DROP WAREHOUSE IF EXISTS BCAST_PLATFORM_NW01_WH;
DROP WAREHOUSE IF EXISTS BCAST_PLATFORM_NW02_WH;
DROP WAREHOUSE IF EXISTS BCAST_PLATFORM_NW03_WH;
DROP WAREHOUSE IF EXISTS BCAST_PLATFORM_NW04_WH;
DROP WAREHOUSE IF EXISTS BCAST_PLATFORM_NW05_WH;
DROP WAREHOUSE IF EXISTS BCAST_PLATFORM_COMMON_WH;
DROP INTEGRATION IF EXISTS BCAST_PLATFORM_GIT_API;
DROP ROLE IF EXISTS BCAST_PLATFORM_ANALYST_ROLE;
DROP ROLE IF EXISTS BCAST_PLATFORM_ENGINEER_ROLE;