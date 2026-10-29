# AI開発ポートフォリオ：初回調査とテーマ選定

調査日：2026年10月28日（日本）。個人のGitHub公開プロジェクトの最初の開発を選ぶための調査です。対象は開発者本人・公式組織の技術記事、公式リポジトリ、リリース記録。世界のエンジニアの順位や、業界全体の統計を調べたものではありません。

## 結論と今回の着手

最初の候補は **Stateful Tool Lab：日本語・英語の業務ツール実行を、実行後の状態で確かめる小さな課題セット** としました。これは以下の一次資料を踏まえた開発上の判断です。

予約登録・キャンセル・変更を題材に、処理の途中で応答が途切れるケース、同じ依頼が届くケース、満席のケースを公開データで再現します。まず評価の土台を実装し、次に既存runnerと実モデルを接続します。差別化の仮説は、明確な業務上の正解、対訳タスク、採点の透明性、失敗例の公開にあります。独創性や需要が実証されたという意味ではありません。

2026年10月28日の到達点は、オフラインの環境・12シナリオ×日英対訳＝24タスク・採点器・scripted controller・trace replayです。AIの自然言語理解、実モデルの性能、利用者の生産性は未測定です。

## 注目する実務者と公開された取り組み

| 実務者・チーム | 一次資料で確認できた事実 | 個人開発への示唆（私たちの判断） |
|---|---|---|
| Nick Hollon / Harrison Chase、LangChain | 2026-07-23の記事で、Harborを用いたエージェント評価を説明。環境・課題・検証スクリプトを揃え、複数試行と成果物の採点を行う。 | コードと一緒に再現環境・課題・採点理由を公開する。 |
| Napalys Klicius、GitHub | 2026-07-10の記事で、コードレビュー用ツールの置換後に悪化し、業務に合わせた指示の調整と評価で改善した事例を報告。 | ツールやモデルを組み合わせるだけでなく、仕事に合う使い方を検証する。 |
| Taylor Mullen / Christian Gunderman、Google | 2026-09-09の記事で、エージェントの具体的な行動を確認する評価と、全体の成果を見る評価の併用を説明。 | 小さな失敗を再現するテストと、最終状態の採点を併せ持つ。 |
| GitHub / Microsoft、HydraFusion | 2026-10-14更新で、工程ごとの推論量調整や、実際のworkspaceを調べる批評処理などを発表。研究プレビュー段階。 | 複数モデルの追加に進む前に、単一方式の品質・コストの基準を作る。 |
| Sierra Research、τ-bench | v2.0.0のリリースノートに2026-10-19と記載。多言語・音声への拡張を発表。記載された6言語はen/es/pt/hi/zh/ko。 | 日本語の小さな課題セットを公開して比較する余地を検討できる。ただし「日本語評価が世界に存在しない」とは言えない。 |
| Pipecatチーム | 2026-10-15のPhoneBench Alpha 2で、複数ターンのツール呼び出しや会話の評価を公開。 | 音声でも、速さ・対話・ツールの成否を分けて測るテーマが有望。 |
| David Koskiほか、MLX Swift LM | 3.32.3の2026-09-30リリースでGuidedGeneration等を追加。 | ローカル生成で、JSONの形式と意味上の正しさを分けて実測する題材がある。 |

上記の事例から、**実行の仕組み・評価・失敗分析を公開する開発には取り組む意義がある**と判断しました。AI業界のすべてがこの方向へ移行した、と断定する調査ではありません。

## 比較した4候補

評価軸は、今の技術的な背景、誰に役立つか、既存OSSとの違い、個人での再現性、GitHubで示せる技術力です。優先度は主観的な選定です。作業日数や市場需要の実測は行っていません。

| 優先度・候補 | 想定利用者と課題 | 独自の成果にできる部分 | 最初の測定 | 依存・不確実性 |
|---|---|---|---|---|
| **第一：Stateful Tool Lab** | 業務エージェントを開発する人。成功したように見えても状態が間違う。 | 日英タスク、業務不変条件、手で指定した正解、失敗例の再現。 | 最終状態、余分／不足の予約、他の予約への変更、正しい結果報告。 | 現在は評価器だけ。実モデルと接続する工程、対訳の人手確認が必要。 |
| 次点：Japanese Voice Regression Kit | 日本語音声エージェントの開発者。言い直し、間、割り込みで失敗する。 | 少量の録音・会話条件、回帰テスト、イベントと音声の対応。 | 応答開始p50/p95、停止までの時間、訂正反映、ツール引数の正解率。 | 録音権利、実際の音声pipeline、モデルの実行環境や利用料。 |
| 次点：Local Tool Calling Lab | Apple SiliconでローカルAIを動かす人。JSONが正しくても引数が誤る。 | 同じタスクで自由生成と制約生成を比較し、日本語の意味上の誤りを分類。 | schema適合率、引数正解率、TTFT、メモリ。 | Apple Silicon実機での計測が必要。今回の環境で性能は測れない。 |
| 後続：Evidence-first Document Extraction | 文書から値を取り出す人。値と出典位置が対応しない。 | 自作の日本語資料、値＋ページ＋位置の採点、誤りの可視化。 | 値の正解率、単位の誤り、根拠位置一致、処理時間。 | 文書処理基盤の依存が大きく、OCR/VLM品質の切り分けが必要。追加調査対象。 |

## 既存OSSとの差と、作りすぎない範囲

| 既存プロジェクト | 確認した役割 | 今回の扱い |
|---|---|---|
| [τ-bench](https://github.com/sierra-research/tau2-bench) | 状態を持つ会話・業務タスクの評価、多言語・音声への展開。 | 設計上の参照先。現在の課題を移植・複製したものではない。日本語拡張への貢献も将来の選択肢。 |
| [Promptfoo](https://github.com/promptfoo/promptfoo) | モデル・エージェント比較、評価設定、CIなど。 | 実モデル接続段階の候補。汎用の比較基盤を一から作る意義は小さい。 |
| [MCP Inspector](https://github.com/modelcontextprotocol/inspector) | MCPサーバーを確認するツール。 | 今回はMCP UIやschema検査を開発対象にしない。 |
| [MCP-Faultline](https://github.com/gigihsusetyo/mcp-faultline) | 故障注入、軌跡の記録、復旧の採点を目的とするMVP。 | 故障注入それ自体は新規性ではない。今後の接続・再利用候補として評価する。 |

現在の環境は、公開タスクと採点を小さく自立して動かすための参照実装です。MCPプロトコルや一般的なfault proxyは実装していません。新しい汎用frameworkとして拡張するより、タスクの品質・人手確認・実モデルの失敗分析を優先します。

## 公開ポートフォリオとして何を示すか

1. **課題を選ぶ判断**：なぜ今この課題かを、日付のある一次資料で説明する。
2. **設計**：ツール応答・本当の状態・採点器を分ける。正解を唯一のツール列に固定しない。
3. **実装**：処理成功後のtimeout、冪等性、原子的な変更、定員制約を再現する。
4. **検証**：意図的に間違える制御、余分な読み取りを許容するテスト、採点をすり抜ける例への回帰テストを揃える。
5. **説明責任**：fixture検証とAI評価の違い、未実施の項目をREADMEに示す。

既存の公開[Review Desk](https://github.com/masaakisakamoto/review-desk)は、具体的な開発体験を改善するプロダクトの軸です。今回の実験は評価・信頼性の軸として並べられます。GitHubの接続一覧は公開リポジトリの完全な目録とは限らないため、この調査では全リポジトリを監査したとは扱いません。

## 次のアクション

今回の初期実装を確認し、次は実モデル接続の方法・利用するモデル・利用料上限を決めます。最初は一つのモデルと二つの方式で条件を揃えて比較し、失敗ごとの実行記録を公開します。詳しい実験条件は[EXPERIMENTS.md](EXPERIMENTS.md)に記載しています。

2026年10月29日追記：[masaakisakamoto/stateful-tool-lab](https://github.com/masaakisakamoto/stateful-tool-lab)としてPublicソースを公開。GitHub Actionsの最新結果はリポジトリのActionsを参照してください。タグ付き公開リリースと実モデル評価は未実施です。

## 一次資料

全て2026-10-28閲覧。記事の日付と、リポジトリを閲覧した日付を区別しています。最新版を使う実験では、別途commit/tagを固定してください。

- **2026-07-23** — Nick Hollon / Harrison Chase, [How We Benchmark Deep Agents](https://www.langchain.com/blog/how-we-benchmark-deep-agents)
- **2026-07-10** — Napalys Klicius, [Better tools made Copilot code review worse](https://github.blog/ai-and-ml/github-copilot/better-tools-made-copilot-code-review-worse-heres-how-we-actually-improved-it/)
- **2026-09-09** — Taylor Mullen / Christian Gunderman, [The Anatomy of Harness Engineering](https://developers.googleblog.com/the-anatomy-of-harness-engineering-how-to-evaluate-iterate-and-guard-ai-coding-agents/)
- **2026-10-14** — GitHub, [HydraFusion updates and new Max option](https://github.blog/changelog/2026-10-14-hydrafusion-updates-and-new-max-option/)
- **リリース本文2026-10-19** — Sierra Research, [τ-bench 2.0.0 releases](https://github.com/sierra-research/tau2-bench/releases)。一覧のUI時刻には10/20表示もあるため、本文のRelease Dateを採用。
- **2026-10-15掲載** — Pipecat, [Benchmarks / PhoneBench Alpha 2](https://www.pipecat.ai/benchmarks)
- **2026-09-30** — MLX Swift LM, [3.32.3 release](https://github.com/ml-explore/mlx-swift-lm/releases/tag/3.32.3)
- **閲覧日現在、公開日未確認** — [Promptfoo repository](https://github.com/promptfoo/promptfoo), [MCP Inspector repository](https://github.com/modelcontextprotocol/inspector), [MCP-Faultline repository](https://github.com/gigihsusetyo/mcp-faultline)

技術的な主張は上記公開資料の範囲に限定しています。テーマの優先度・貢献可能性は推論であり、利用者への需要調査や競合の網羅調査は未実施です。
