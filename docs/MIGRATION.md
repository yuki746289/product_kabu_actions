# product_kabu Actions 分離移行

## 目的

- `product_kabu`: 開発コード、ロジック、テスト、仕様を保持し、移行完了後に private 化する。
- `product_kabu_actions`: public の GitHub Actions 実行基盤として使用する。
- private リポジトリ側では GitHub Actions を実行しない。

## 実行方式

public workflow は実行時だけ `product_kabu` を `_core/` に checkout する。

- `_core/` は `.gitignore` 対象で public repository にはコミットしない。
- private source 取得には `KABU_PRIVATE_REPO_TOKEN` を使う。
- public workflow から private source への書き込みは行わない。
- public 側で保持するデータや Artifact への書き込みは `product_kabu_actions` の `GITHUB_TOKEN` を使う。

## Secret

`product_kabu_actions` の Repository secret に次を登録する。

- Name: `KABU_PRIVATE_REPO_TOKEN`
- 推奨: Fine-grained personal access token
- Repository access: `product_kabu` のみ
- Repository permissions: `Contents: Read`

Secret は workflow やログへ直接出力しない。

## セキュリティ方針

private source を取得する workflow は `workflow_dispatch` / `schedule` を基本とする。
外部 pull request から private token を使用する構成にはしない。

## 移行判定

次の全条件を満たすまで `product_kabu` を private 化しない。

1. public Actions から `product_kabu` を token 付きで checkout できる。
2. `scripts/check_screening_regressions.py` が public runner 上で PASS する。
3. 日次スクリーニング一式を public runner へ移し、結果・Artifact が正常に生成される。
4. P1 300D / P2 60D を含む主要ヒストリカル検証が public runner で成功する。
5. public workflow の schedule を有効化する。
6. `product_kabu` 側の workflow を無効化または削除し、private Actions を消費しない状態にする。
7. private 化後にもう一度 public Actions から checkout と主要パイプラインが成功することを確認する。

条件6まで完了した時点で private 化を案内し、条件7を最終スモークテストとする。
