# product_kabu_actions

`product_kabu` の実行基盤を分離するための public GitHub Actions リポジトリです。

- `product_kabu`: 開発コード・ロジック・仕様・テスト・生成データを管理（移行完了後 private）
- `product_kabu_actions`: GitHub Actions 実行基盤と公開 Artifact を管理（public）

## 基本方針

public Actions は実行時だけ `product_kabu` を checkout し、その runner 上で処理します。private source は `product_kabu_actions` へコミットしません。

Repository secret `KABU_PRIVATE_REPO_TOKEN` を使用し、`product_kabu` の `Contents: Read and write` のみに権限を限定します。書き込みは日次生成データを `product_kabu` へ保存するために使用します。

private 側の GitHub Actions は使用しません。

## 移行状況

現在は移行準備中です。`product_kabu` の private 化は、public runner 上で日次スクリーニングと主要バックテストまで検証し、private 側 workflow を停止した後に行います。

詳細は `docs/MIGRATION.md` を参照してください。
