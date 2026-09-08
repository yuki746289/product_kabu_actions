# product_kabu Actions 分離移行

## 目的

- `product_kabu`: 開発コード、ロジック、テスト、仕様、生成データを保持し、移行完了後に private 化する。
- `product_kabu_actions`: public の GitHub Actions 実行基盤として使用する。
- private リポジトリ側では GitHub Actions を実行しない。

## 実行方式

public workflow は実行時だけ `product_kabu` を checkout して、その public runner 上で処理する。

- private source は `product_kabu_actions` へコミットしない。
- private repo 取得には `KABU_PRIVATE_REPO_TOKEN` を使う。
- スクリーニングやデータ更新で `product_kabu/data` に変更が出た場合は、public runner から同じ token で `product_kabu` へ commit/push する。
- 実行ログと Actions Artifact は public 側に出るため、機密情報や token を出力しない。

この方式により、既存の `product_kabu` の相対パス・データ構成を大きく変えずに Actions の実行場所だけ public 側へ移せる。

## Secret

`product_kabu_actions` の Repository secret に次を登録する。

- Name: `KABU_PRIVATE_REPO_TOKEN`
- 推奨: Fine-grained personal access token
- Repository access: `product_kabu` のみ
- Repository permissions: `Contents: Read and write`

書き込み権限は、日次データ更新結果を `product_kabu` へ保存するために使用する。Issues、Pull requests、Administration 等の追加権限は不要。

## セキュリティ方針

private source/token を使う workflow は `workflow_dispatch` / `schedule` を基本とする。
外部 pull request から private token を使用する構成にはしない。

`persist-credentials` が必要な production workflow では、用途を `product_kabu` の fetch/push に限定する。診断用 smoke test では書き込みを行わない。

## 移行判定

次の全条件を満たすまで `product_kabu` を private 化しない。

1. public Actions から `product_kabu` を token 付きで checkout できる。
2. `scripts/check_screening_regressions.py` が public runner 上で PASS する。
3. 日次スクリーニング一式を public runner へ移し、生成データの `product_kabu` への commit/push と Artifact 生成が正常に完了する。
4. P1 300D / P2 60D を含む主要ヒストリカル検証が public runner で成功する。
5. public workflow の schedule を有効化する。
6. `product_kabu` 側の workflow を無効化または削除し、private Actions を消費しない状態にする。
7. `product_kabu` を private 化する。
8. private 化後にもう一度 public Actions から checkout、日次パイプライン、主要検証が成功することを確認する。

条件6まで完了した時点で private 化を案内し、条件8を最終スモークテストとする。
