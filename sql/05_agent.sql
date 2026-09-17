-- GUI が主経路です。docs/05_agent.md と docs/agent_texts.md を先に開いてください。
-- 全選択で実行しないでください。以下は対象教材環境で参加者が選択実行する手順です。
-- 再生成した2026年5月から7月の教材用。今回のSQL・GUI/CoWorkは未検証。
USE ROLE BCAST_PLATFORM_ENGINEER_ROLE;
USE WAREHOUSE BCAST_PLATFORM_COMMON_WH;

-- CHECKPOINT: GUI で MART.VIEWING_AGENT を作成・設定・保存するまでここで停止。
-- ツールは SV_VIEWING (Cortex Analyst) の1つだけ。
-- Auto、BCAST_PLATFORM_COMMON_WH、Query timeout 120秒を確認する。
SHOW AGENTS IN SCHEMA BCAST_PLATFORM_HANDSON.MART;
DESCRIBE AGENT BCAST_PLATFORM_HANDSON.MART.VIEWING_AGENT;

-- GUI の保存内容を確認後に実行。所有者または対象 GRANT を行えるロールが必要です。
GRANT USAGE ON AGENT BCAST_PLATFORM_HANDSON.MART.VIEWING_AGENT
  TO ROLE BCAST_PLATFORM_ANALYST_ROLE;

-- 保険: GUI でまだ Agent を作っていない場合のみ、このコメント内の SQL を選択実行。
-- CREATE OR REPLACE は使わず、同名オブジェクトの上書きを防ぎます。
-- GUI の文章と設定値を合わせていますが、GUI/SQL の動作同等性は未検証です。
-- 実行後は上の SHOW/DESCRIBE/GRANT と GUI の保存・公開確認に戻ってください。
/*
CREATE AGENT BCAST_PLATFORM_HANDSON.MART.VIEWING_AGENT
  COMMENT = '地上波5局の合成視聴データを、日付・放送局・ジャンル別に集計する日本語の分析エージェントです。リーチ、総視聴時間、総視聴回数を扱います。'
  PROFILE = '{"display_name":"5局共通の視聴データ分析"}'
  FROM SPECIFICATION
$$
models:
  orchestration: auto
instructions:
  orchestration: |
    視聴実績の数値・比較・推移は必ず SV_VIEWING を使って取得してください。
    対象は BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY に基づく実績だけです。
    リーチは対象範囲全体で DEVICE_ID の重複を除いて計算し、日別・局別・ジャンル別のリーチを足さないでください。
    総視聴時間は VIEW_MINUTES の合計、総視聴回数は SESSION_COUNT の合計です。行数を視聴回数にしないでください。
    視聴区間全体を開始日と開始時のジャンルに計上しています。番組ごとの正確な視聴時間とは説明しないでください。
    期間が省略されたら2026-05-01から2026-07-31、局が省略されたら全5局を対象にして、その範囲を明示してください。指定された期間・局を勝手に置き換えないでください。
    ジャンルは NEWS（ニュース）、DRAMA（ドラマ）、VARIETY（バラエティ）、ANIME（アニメ）、SPORTS（スポーツ）、MUSIC（音楽）、MOVIE（映画）、INFO（情報）、UNKNOWN（分類不明）、局は NW01からNW05です。
    F1（20〜34歳の女性）の同居確率・同居予測・実際のF1視聴者数・モデル評価・性年代・番組内容の検索・広告接触・分別曲線はこのツールの対象外です。実績から推測せず、対象外と説明してください。
    ツールが失敗した場合は数値を生成せず、失敗を伝えてください。
  response: |
    日本語で簡潔に答え、数値には対象期間・放送局・ジャンル条件と単位を添えてください。
    リーチは端末数であり、人数や世帯数ではありません。合成データの教材であることを示してください。
    複数行の比較結果は表にし、リーチの内訳を足して全体値を作らないでください。
    データがない場合は取得結果に従って該当データなしと説明し、未実行・エラーをゼロ件と扱わないでください。
    参照元として BCAST_PLATFORM_HANDSON.MART.SV_VIEWING を示してください。未検証の推定や因果関係を事実として述べないでください。
  sample_questions:
    - question: '2026年5月1日から7月31日の全5局のリーチ、総視聴時間、総視聴回数を教えてください'
    - question: '2026年5月1日から7月31日の放送局別リーチを比較してください'
    - question: '2026年7月1日から7日のNW01のジャンル別総視聴時間を教えてください'
tools:
  - tool_spec:
      type: cortex_analyst_text_to_sql
      name: SV_VIEWING
      description: |
        5局の合成視聴実績を集計します。リーチは DEVICE_ID の重複を除いた端末数、総視聴時間は VIEW_MINUTES の合計（分）、総視聴回数は SESSION_COUNT の合計です。
        切り口は視聴日・放送局・ジャンル。データ期間は2026-05-01から2026-07-31です。予測値・正解ラベル・番組説明・分別曲線は扱いません。
tool_resources:
  SV_VIEWING:
    semantic_view: BCAST_PLATFORM_HANDSON.MART.SV_VIEWING
    execution_environment:
      type: warehouse
      warehouse: BCAST_PLATFORM_COMMON_WH
      query_timeout: 120
$$;
*/