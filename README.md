# Budget Guru – LLMOps サンプルアプリ

**Datadog Agent Observability**（LLM Observability）と **Datadog LLM Experiments / Datasets** を活用した、LLMOps のサンプル実装です。

## 概要

「若者向け投資アシスタント（Budget Guru）」を題材に、以下を学べます。

- LLM アプリを Datadog Agent Observability に計測させる方法
- Dataset / Experiments を設計して「プロンプトやモデルの変更の良し悪し」を数値で比較する方法
- 将来的に CI/CD に組み込める形で Experiments ランナーを構成する方法

| コンポーネント | 説明 |
|---|---|
| `app/` | FastAPI チャット API（Budget Guru） |
| `experiments/` | オフライン評価ランナー（Datadog Experiments 連携） |
| `datasets/` | 評価用 Q&A CSV（日本語・12件） |

---

## 前提条件

- Python 3.11 以上
- OpenAI API キー（または互換エンドポイント）
- Datadog アカウント（API キー・APP キー・サイト）

---

## セットアップ

```bash
# 1. 仮想環境の作成と有効化
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. 依存パッケージのインストール
pip install -r requirements.txt

# 3. 環境変数の設定
cp .env.example .env
# .env を編集して各種キーを入力
```

### 環境変数一覧

| 変数名 | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `OPENAI_API_KEY` | ✅ | — | LLM プロバイダーの API キー |
| `LLM_MODEL` | — | `gpt-4.1` | 使用するモデル名 |
| `LLM_TIMEOUT` | — | `60` | LLM 呼び出しのタイムアウト（秒） |
| `DD_API_KEY` | ✅ | — | Datadog API キー |
| `DD_APP_KEY` | ✅ | — | Datadog APP キー |
| `DD_SITE` | — | `datadoghq.com` | Datadog サイト |
| `DD_LLMOBS_ENABLED` | — | `false` | LLM Observability の有効化 |
| `DD_LLMOBS_ML_APP` | — | `budget-guru-ml-app` | Datadog UI に表示される ML アプリ名 |
| `DD_LLMOBS_PROJECT_NAME` | — | `budget-guru-experiments` | Experiments のプロジェクト名 |
| `DD_LLMOBS_AGENTLESS_ENABLED` | — | `false` | Agentless モード（Agent 不要で直接送信） |
| `DD_TRACE_ENABLED` | — | `true` | APM トレースの有効化 |

---

## チャット API の起動

```bash
uvicorn app.main:app --reload
```

### ヘルスチェック

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### チャットエンドポイント

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-001",
    "message": "ETFとは何ですか？",
    "prompt_variant": "P4"
  }'
```

レスポンス例：

```json
{
  "answer": "ETFは「上場投資信託」の略で...",
  "prompt_variant": "P4",
  "model": "gpt-4.1"
}
```

`prompt_variant` に `P1`〜`P4` を指定することで、異なるシステムプロンプトで回答を生成できます。

---

## プロンプトバリアント（P1〜P4）

`app/prompts.py` に定義されています。

| バリアント | 特徴 |
|---|---|
| **P1** | 標準的な金融アシスタント |
| **P2** | 高度な専門家向け（詳細・専門用語多め） |
| **P3** | 小学生向け（超シンプル・短め） |
| **P4** | 20代向けフレンドリー（友達口調・具体例あり） |

---

## Datadog Agent Observability の設定

1. `.env` で `DD_LLMOBS_ENABLED=true` に設定
2. `DD_API_KEY`、`DD_SITE` を入力
3. アプリを起動してリクエストを送信
4. **Datadog → LLM Observability → Traces** でスパンを確認

Datadog Agent が不要な場合は `DD_LLMOBS_AGENTLESS_ENABLED=true` に設定してください。

---

## Experiments の実行

### Dataset について

`datasets/budget_guru_investment_qa.csv` に 12 件の投資 Q&A が含まれています。

| カラム | 説明 |
|---|---|
| `id` | レコード ID |
| `input` | ユーザーの質問 |
| `expected_output` | 模範回答 |
| `topic` | トピック（例: etf, budgeting） |
| `difficulty` | 難易度（beginner / intermediate） |
| `age_group` | 対象年齢層 |

### 実行コマンド

```bash
python -m experiments.run_experiments \
  --dataset ./datasets/budget_guru_investment_qa.csv \
  --models gpt-4.1 \
  --prompts P1 P2 P3 P4
```

### 実行内容

1. CSV を Datadog に Dataset として登録
2. `model × prompt` の組み合わせごとに Experiment を実行
3. 各レコードに対して LLM で回答を生成
4. 3つの Evaluator でスコアリング
   - `contains_keywords_eval` — キーワード網羅率（0〜1）
   - `information_accuracy` — 情報の正確さ（LLM-as-a-judge、0〜1）
   - `brand_voice_consistency` — 若者向けトーンか（LLM-as-a-judge、true/false）
5. 結果を Datadog Experiments UI に送信

### コンソール出力例

```
INFO Registering dataset: ./datasets/budget_guru_investment_qa.csv
INFO Dataset registered.
INFO Running experiment: budget-guru-gpt-4.1-P1
INFO Running experiment: budget-guru-gpt-4.1-P4
...
View in Datadog: https://app.datadoghq.com/llm/experiments/xxxxx
All experiments completed.
```

---

## カスタマイズガイド

| 変更したい内容 | 該当ファイル |
|---|---|
| システムプロンプト（P1〜P4）の変更 | `app/prompts.py` |
| LLM プロバイダー・モデルの変更 | `app/config.py` + 環境変数 |
| Evaluator のロジック変更 | `experiments/evaluators.py` |
| Dataset の追加・変更 | `datasets/budget_guru_investment_qa.csv` |
| Datadog Dataset 登録の実装 | `experiments/datasets.py` |
| Datadog Experiments 送信の実装 | `experiments/run_experiments.py` |

---

## ディレクトリ構成

```
.
├── app/
│   ├── main.py                    # FastAPI エントリポイント
│   ├── config.py                  # 環境変数設定
│   ├── llm_client.py              # LLM クライアント（openai SDK）
│   ├── prompts.py                 # システムプロンプト P1〜P4
│   └── datadog_instrumentation.py # Datadog APM + LLM Obs 初期化
├── experiments/
│   ├── datasets.py                # CSV ローダー
│   ├── evaluators.py              # Evaluator 定義
│   └── run_experiments.py         # Experiments ランナー CLI
├── datasets/
│   └── budget_guru_investment_qa.csv  # 評価用 Q&A（日本語・12件）
├── requirements.txt
├── .env.example
└── README.md
```
