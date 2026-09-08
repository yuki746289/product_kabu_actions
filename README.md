# product_kabu_actions

`product_kabu` の実行基盤を分離するための public GitHub Actions リポジトリです。

- `product_kabu`: 開発コード・ロジック・仕様を管理（移行完了後 private）
- `product_kabu_actions`: GitHub Actions、公開可能なデータ・Artifact を管理（public）

移行中は `product_kabu` を private 化せず、public 側 Actions の動作確認完了後に切り替えます。
