# product_kabu_actions

`product_kabu` の実行基盤を分離するための public GitHub Actions リポジトリです。

- `product_kabu`: 開発コード・ロジック・仕様・テストを管理（移行完了後 private）
- `product_kabu_actions`: GitHub Actions、公開可能なデータ・Artifact を管理（public）

## 基本方針

public Actions は実行時だけ `product_kabu` を `_core/` に checkout します。private source は public repository へコミットしません。

private source の取得には Repository secret `KABU_PRIVATE_REPO_TOKEN` を使用します。推奨権限は `product_kabu` の `Contents: Read` のみです。

private 側の GitHub Actions は使用しません。

## 移行状況

現在は移行準備中です。`product_kabu` の private 化は、public runner 上で日次スクリーニングと主要バックテストまで検証してから行います。

詳細は `docs/MIGRATION.md` を参照してください。
