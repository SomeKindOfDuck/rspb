# rspb

実験制御用の Raspberry Pi に、開発環境と `flkl` の `pj-yoneyama` ブランチを導入します。
対象は **64bit Ubuntu / Raspberry Pi OS（arm64 / amd64）** です。
R・Julia・Claude Code・Codex は導入しません。

## 最初に実行するコマンド

sudo を使える通常ユーザーで実行します。スクリプト全体を `sudo` で実行しないでください。
以下は既定の配置先を使う手順です。各段階が完了してから、次の段階に進んでください。

### 1. リポジトリを取得してセットアップする

```sh
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/SomeKindOfDuck/rspb "$HOME/.rspb"
cd "$HOME/.rspb"
bash init.sh
```

すでに clone 済みなら、上の `git clone` の代わりに次で更新してから `bash init.sh` を実行します。

```sh
cd "$HOME/.rspb"
git pull --ff-only
bash init.sh
```

**`bash init.sh` が、依存ツールの導入、`flkl/pj-yoneyama` と Python 環境の準備、
dotfiles の取得・Pi 用パッチの適用・`chezmoi apply`、Neovim の初期設定まで自動で行います。**
最後に `Setup complete.` で始まるメッセージが出たら完了です。
途中でエラーになった場合は原因を解消し、同じディレクトリで `bash init.sh` を再実行してください。

### 2. dotfiles が反映されたことを確認する

まだ元のシェルでは PATH が更新されていないことがあるため、ここでは実行ファイルを絶対パスで指定します。

```sh
# Pi 上の chezmoi ソースディレクトリを表示
"$HOME/.local/bin/chezmoi" source-path

# 適用先がソースと一致するか確認（終了コード 0 なら反映済み）
"$HOME/.local/bin/chezmoi" verify
```

`chezmoi apply` は手順 1 の中で実行済みです。差分を確認して再適用する必要がある場合は、次を実行します。

```sh
"$HOME/.local/bin/chezmoi" diff
"$HOME/.local/bin/chezmoi" apply
"$HOME/.local/bin/chezmoi" verify
```

### 3. fish とシリアルポートの権限を反映する

対話端末では `init.sh` の最後にログインシェルを fish に変更します。
非対話実行などで `chsh` の案内が表示された場合だけ、次を実行してください。

```sh
chsh -s /usr/bin/fish
```

作業を保存して再起動し、同じユーザーでログインし直します。
再起動の代わりに、デスクトップや SSH セッションからログアウトして再ログインしても構いません。
これでログインシェルと `dialout` グループが反映されます。

```sh
sudo reboot
```

### 4. ログインし直して環境と Arduino を確認する

Arduino Uno R3 を 1 台接続して、次を実行します。

```sh
# /usr/bin/fish と、dialout を含むグループ一覧を確認
echo "$SHELL"
id -nG

# dotfiles の反映と flkl のブランチ・Python・CLI を確認
chezmoi verify
cd "$HOME/Programs/Github/flkl"
git branch --show-current
uv run --locked --no-dev python --version
uv run --locked --no-dev train --help

# Arduino の認識を確認
arduino-cli board list
```

ブランチが `pj-yoneyama`、Python が `3.10.x` であることを確認します。
`arduino-cli board list` では接続した Arduino のポートとボード情報を確認してください。

### 5. 実験設定を編集して実行する

設定ファイルは `init.sh` がサンプルから作成済みです。装置の配線と実験条件に合わせて編集します。

```sh
cd "$HOME/Programs/Github/flkl"
nvim config/train.yaml
nvim config/test.yaml
```

準備ができたら、実行したい方のコマンドを選びます。`M01` は実際の被験体 ID に置き換えてください。
**ここからは Arduino へスケッチを書き込み、実際に装置を動かします。**

training を実行する場合：

```sh
cd "$HOME/Programs/Github/flkl"
uv run --locked --no-dev train M01 config/train.yaml
```

test を実行する場合：

```sh
cd "$HOME/Programs/Github/flkl"
uv run --locked --no-dev test M01 config/test.yaml
```

### 6. flkl の準備だけをやり直す場合

uv と Arduino CLI が使える状態で、次を実行します。

```sh
cd "$HOME/.rspb"
bash scripts/setup-flkl.sh
```

## セットアップについて

公開リポジトリを HTTPS で取得するため、GitHub アカウントへのログインは不要です。
ツールは各公式配布元の安定版を導入します。Rust 製ツールのビルドには時間がかかります。
arm64 ではメモリ使用量を抑えるため `CARGO_BUILD_JOBS=1` を既定値にします。
途中で失敗した場合はその場で停止します。

## 導入内容

| 対象 | 内容 |
| --- | --- |
| シェル・操作 | fish、fzf、direnv、tmux、bottom、eza、fd、ripgrep、Starship |
| ターミナル | Alacritty、Hack Nerd Font、X11 / Wayland 用クリップボード |
| エディター | 最新安定版 Neovim、clangd、pynvim、isort、IPython |
| Python | uv と uv 管理の安定版 Python 3。flkl 用には別途 Python 3.10 |
| JavaScript | fnm による最新 Node.js LTS、Corepack、Yarn |
| ビルド・音声 | stable Rust、C/C++ ツール、cmake、pkg-config、PortAudio など |
| Arduino | 公式 Arduino CLI、`arduino:avr` コア、`Servo`、`dialout` グループ |
| dotfiles | 現在のローカル chezmoi と同じリポジトリを基に、Pi 用の修正を適用 |
| flkl | `pj-yoneyama` の取得、lockfile に沿った依存導入、CLI とスケッチの検証 |

pyenv・Poetry・Anaconda の新規導入はありません。既存のシステム環境や過去のインストールは削除しません。

## flkl / pj-yoneyama

既定の配置先は `~/Programs/Github/flkl` です。
新規環境では [SomeKindOfDuck/flkl](https://github.com/SomeKindOfDuck/flkl/tree/pj-yoneyama) の
`pj-yoneyama` ブランチを取得します。既存の同ブランチの作業コピーは、pull や上書きをせず再利用します。
別ブランチや不完全なディレクトリがある場合は停止します。

セットアップは次を行います。

1. `.python-version` で指定された Python を導入（確認した版では **3.10**）。
2. `uv sync --locked --no-dev` でプロジェクトの `.venv` を作成。
3. Python 依存の import と `train` / `test` / `blink` の `--help` を確認。
4. 同じ版の `ino/ino.ino` と `ino/equal_on.h` を、既定では Uno R3 用にコンパイル。
5. 未作成の場合だけ `config/train.yaml` と `config/test.yaml` をサンプルから作成。

Arduino へのアップロードや実験開始はセットアップ中には行いません。
このスケッチは AVR のレジスターを直接使用するため、Uno R3 / ATmega328P を前提とします。
Uno R4 など別 MCU のボードは、コアの追加だけでは対応できません。

実験時は再ログイン後に **flkl のルートディレクトリから** 実行します。
設定の `sketch: ./ino` とログの保存先が、カレントディレクトリ基準だからです。

`train` / `test` / `blink` は起動時に Arduino へスケッチを書き込みます。
認識できる Arduino を 1 台接続し、ポートのアクセス権と配線を確認してください。
`--no-dev` は flkl の旧 `python-language-server` など、実験実行に不要な開発依存の導入を避けます。
Python 3.10 と lockfile を維持し、システムの最新 Python を実験環境に流用しません。

Pi は実験制御を担当します。`monitor` の作図や R による解析は別の解析用 PC で実行してください。

## 現在の dotfiles の利用

参照元はローカル chezmoi の `/home/duck/Programs/Github/dotfiles` と同じ
[SomeKindOfDuck/dotfiles](https://github.com/SomeKindOfDuck/dotfiles) です。
確認したコミット `1dac187d2fc504111fcd5f33f9b6559662f30599` を取得し、
[Pi 用パッチ](patches/raspberry-pi.patch) を適用してから `chezmoi apply` を実行します。
新しい upstream の変更でパッチが突然適用できなくならないよう、基準コミットを固定しています。

- fish / Bash の固定された `/home/duck`、pyenv、Anaconda の参照を整理し、uv / fnm の PATH を設定。
- fish の eza エイリアスと `.venv` の自動切替を整備。手動で有効化した仮想環境は維持。
- Alacritty の旧 YAML のテーマ・フォントを TOML に統合し、既存の Shift+Enter 設定を維持。
- Neovim の Python REPL を `uv run --no-dev --with ipython ipython` に変更し、pynvim を設定。
- R / Julia の REPL・補完・パーサーと Claude Code 連携を除外。
- ローカルで使っている CoC 補完のうち Lua、pairs、Pyright、snippets、JSON、clangd、HTML を導入。
- coc.nvim は参照版の `package-lock.json` に合わせて `npm ci` でビルド。

Neovim プラグインは dotfiles の `lazy-lock.json` に合わせ、パーサーと補完拡張も初期導入します。
パッチは Pi の chezmoi ソースにローカル変更として残ります。デスクトップの元リポジトリへの
変更、commit / push、秘密情報や認証情報のコピーは行いません。
再実行時は適用済みのパッチを維持し、競合する手元の変更がある場合は上書きせず停止します。
上流 dotfiles を更新する際は、基準コミットとパッチを一緒に見直してください。

## 設定の変更

環境変数は `bash init.sh` の前に指定できます。

| 変数 | 既定値・用途 |
| --- | --- |
| `RSPB_FLKL_DIR` | `$HOME/Programs/Github/flkl`。既存の pj-yoneyama 作業コピーも指定可能 |
| `RSPB_INIT_FLKL` | `1`。`0` で flkl の取得・依存導入・検証を省略 |
| `RSPB_ARDUINO_FQBN` | `arduino:avr:uno`。対応する AVR ボードのコンパイル確認に使用 |
| `RSPB_INIT_NVIM` | `1`。`0` でプラグイン等の初期取得を省略 |
| `RSPB_PYTHON_VERSION` | `3`。汎用 Python の指定。flkl は自身の `.python-version` を使用 |
| `RSPB_DOTFILES_REPO` | `https://github.com/SomeKindOfDuck/dotfiles`。基準コミットを含むミラー等を指定 |
| `CARGO_BUILD_JOBS` | arm64 は `1`、amd64 は Cargo の既定値 |

汎用の Python プロジェクトでは `uv init`、`uv add`、`uv sync`、`uv run` を使用します。
uv は標準で `.venv` を作成するため、Poetry の `virtualenvs.in-project` 相当の設定は不要です。
既存の Poetry プロジェクトの `pyproject.toml` や lockfile は、このスクリプトでは変換しません。

## 検証

シェル構文・ShellCheck に加え、実際の chezmoi による一時 HOME への適用と再実行、
fish の仮想環境切替、Alacritty TOML、Neovim 設定、競合時の保護を確認できます。
Python 3.11 以上、chezmoi、fish、Neovim、git が必要です。

```sh
python3 tests/check_dotfiles.py /path/to/dotfiles
```

確認した `flkl/pj-yoneyama` は `127b5238c1fe2fdfcb5ff0fe7bb58b018443decf` です。
x86_64 の一時環境で Python 3.10 の依存導入・CLI 起動、Arduino CLI 1.5.1 / AVR 1.8.8 による
Uno 向けコンパイルを確認しました。ARM64 は依存の解決と配布物を確認しています。
Pi 実機でのインストール・USB 認識・ポート権限・音声出力・配線と刺激動作は未検証です。

## 公式手順

- [uv のインストール](https://docs.astral.sh/uv/getting-started/installation/) / [lockfile と同期](https://docs.astral.sh/uv/concepts/projects/sync/)
- [Neovim](https://github.com/neovim/neovim/blob/master/INSTALL.md) / [chezmoi](https://www.chezmoi.io/install/)
- [fnm](https://github.com/Schniz/fnm#installation) / [Yarn](https://yarnpkg.com/getting-started/install)
- [eza](https://github.com/eza-community/eza/blob/main/INSTALL.md) / [Alacritty](https://github.com/alacritty/alacritty/blob/master/INSTALL.md)
- [Arduino CLI](https://arduino.github.io/arduino-cli/latest/installation/)
