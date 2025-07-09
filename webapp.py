# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import pytz
import os
import io

# --- 元々の処理関数 ---
# messageboxをStreamlitの通知機能(st.errorなど)に置き換える以外は、ほぼそのまま流用

def convert_encoding(uploaded_file):
    """アップロードされたファイルの内容をUTF-8に変換する"""
    try:
        content = uploaded_file.getvalue()
        encodings = ['shift_jis', 'cp932', 'euc_jp', 'utf-8']
        decoded_content = None

        for enc in encodings:
            try:
                decoded_content = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if decoded_content is None:
            st.error("適切なエンコーディングを検出できませんでした。")
            return None

        return decoded_content
    except Exception as e:
        st.error(f"ファイルのエンコーディング変換中にエラーが発生しました: {e}")
        return None

def process_gmo_history(df, selected_brand, start_trade_index, end_trade_index):
    """CSVデータを処理して取引リストを作成する"""
    try:
        nq100_df = df[df['銘柄名'] == selected_brand].copy()

        if nq100_df.empty:
            st.info(f"{selected_brand} の取引履歴が見つかりませんでした。")
            return pd.DataFrame()

        col_約定日時 = [col for col in df.columns if '約定日時' in col][0]
        col_取引区分 = [col for col in df.columns if '取引区分' in col][0]
        col_売買区分 = [col for col in df.columns if '売買区分' in col][0]
        col_約定単価 = [col for col in df.columns if '約定単価' in col][0]
        col_約定数量 = [col for col in df.columns if '約定数量' in col][0]
        col_実現損益 = [col for col in df.columns if '実現損益' in col][0]

        nq100_df = nq100_df[[col_約定日時, col_取引区分, col_売買区分, col_約定単価, col_約定数量, col_実現損益]]

        jst = pytz.timezone('Asia/Tokyo')
        nq100_df[col_約定日時] = pd.to_datetime(nq100_df[col_約定日時]).dt.tz_localize(jst, ambiguous='infer')

        nq100_df['PineTimestamp'] = nq100_df[col_約定日時].apply(
            lambda x: f'timestamp("GMT+9", {x.year}, {x.month}, {x.day}, {x.hour}, {x.minute}, {x.second})'
        )
        nq100_df['TradeID'] = [f'trade{i+1}' for i in range(len(nq100_df))]
        nq100_df[col_実現損益] = pd.to_numeric(nq100_df[col_実現損益], errors='coerce')

        def get_trade_category(row):
            if row[col_取引区分] in ['CFD新規', 'FXネオ新規']:
                return 'Le' if row[col_売買区分] == '買' else 'Se'
            elif row[col_取引区分] in ['CFD決済', 'CFDロスカット', 'FXネオ決済', 'FXネオロスカット']:
                if row[col_売買区分] == '売':
                    return 'Lg' if row[col_実現損益] >= 0 else 'Ll'
                elif row[col_売買区分] == '買':
                    return 'Sg' if row[col_実現損益] >= 0 else 'Sl'
            return 'Unknown'

        nq100_df['TradeCategory'] = nq100_df.apply(get_trade_category, axis=1)
        processed_df = nq100_df.iloc[start_trade_index-1:end_trade_index]
        return processed_df

    except Exception as e:
        st.error(f"データの処理中にエラーが発生しました: {e}")
        return pd.DataFrame()

def update_pinescript(pinescript_template_path, processed_trades_data, selected_brand):
    """テンプレートと取引データからPine Scriptを生成する"""
    try:
        # 先にデータが空でないかチェック
        if not processed_trades_data:
            st.info("処理対象の取引履歴データがありません。")
            return None

        with open(pinescript_template_path, 'r', encoding='utf-8') as f:
            pinescript_content = f.read()

        # <銘柄名F> を選択された銘柄名に置換
        pinescript_content = pinescript_content.replace('<銘柄名F>', selected_brand)

        start_marker = '//trade1'
        end_marker = '//trade1_fin'
        start_index = pinescript_content.find(start_marker)
        end_index = pinescript_content.find(end_marker)

        if start_index == -1 or end_index == -1:
            st.error(f"Pine Scriptテンプレートにマーカーが見つかりません。")
            return None

        end_index += len(end_marker)
        trade_block_template = pinescript_content[start_index:end_index]
        content_before_template = pinescript_content[:start_index]
        content_after_template = pinescript_content[end_index:]

        generated_trade_blocks = []
        # キーを動的に取得
        price_key = [key for key in processed_trades_data[0].keys() if '約定単価' in key][0]
        quantity_key = [key for key in processed_trades_data[0].keys() if '約定数量' in key][0]
        pnl_key = [key for key in processed_trades_data[0].keys() if '実現損益' in key][0]

        for i, trade_data in enumerate(processed_trades_data):
            trade_num = i + 1
            current_trade_block = trade_block_template
            # プレースホルダーを動的に置換
            current_trade_block = current_trade_block.replace(f'trade1', f'trade{trade_num}')
            current_trade_block = current_trade_block.replace(f'<1A>', f'<{trade_num}A>')
            current_trade_block = current_trade_block.replace(f'<1B>', f'<{trade_num}B>')
            current_trade_block = current_trade_block.replace(f'<1C>', f'<{trade_num}C>')
            current_trade_block = current_trade_block.replace(f'<1D>', f'<{trade_num}D>')
            current_trade_block = current_trade_block.replace(f'<1E>', f'<{trade_num}E>')

            # 値を置換
            current_trade_block = current_trade_block.replace(f'<{trade_num}A>', trade_data['PineTimestamp'])
            current_trade_block = current_trade_block.replace(f'<{trade_num}B>', trade_data['TradeCategory'])
            current_trade_block = current_trade_block.replace(f'<{trade_num}C>', str(trade_data[price_key]))
            current_trade_block = current_trade_block.replace(f'<{trade_num}D>', str(trade_data[quantity_key]))
            current_trade_block = current_trade_block.replace(f'<{trade_num}E>', str(trade_data[pnl_key]))
            generated_trade_blocks.append(current_trade_block)

        final_pinescript_content = (
            content_before_template +
            '\n'.join(generated_trade_blocks) +
            content_after_template
        )
        return final_pinescript_content
    except Exception as e:
        st.error(f"Pine Scriptの生成中にエラーが発生しました: {e}")
        return None

# --- Streamlit UI ---
st.title("Trade Plotter for Pine Script")

# 1. CSVファイルアップロード
st.header("1. 取引履歴CSVファイルをアップロード")
uploaded_file = st.file_uploader("GMOクリック証券の取引履歴CSVを選択してください", type=["csv"])

if uploaded_file is not None:
    decoded_content = convert_encoding(uploaded_file)
    if decoded_content:
        try:
            # 文字列IOを使ってpandasで読み込み
            csv_io = io.StringIO(decoded_content)
            all_trades_df = pd.read_csv(csv_io)

            if '銘柄名' not in all_trades_df.columns:
                st.error("CSVファイルに '銘柄名' カラムが見つかりません。")
            else:
                # 2. 銘柄選択
                st.header("2. 銘柄を選択")
                unique_brands = all_trades_df['銘柄名'].unique().tolist()
                selected_brand = st.selectbox("銘柄を選択してください", unique_brands)

                if selected_brand:
                    # 3. 取引範囲選択
                    st.header("3. Pine Scriptにプロットする取引の範囲を選択")
                    brand_trades_df = all_trades_df[all_trades_df['銘柄名'] == selected_brand]
                    total_trades = len(brand_trades_df)
                    st.write(f"選択中の銘柄の総取引数: {total_trades}件")

                    # 2列レイアウト
                    col1, col2 = st.columns(2)
                    with col1:
                        start_index = st.number_input("開始No.", min_value=1, max_value=total_trades, value=1, step=1)
                    with col2:
                        # デフォルトの終了No.は、最大200件の範囲に収まるように調整
                        default_end_index = min(start_index + 199, total_trades)
                        end_index = st.number_input("終了No.", min_value=start_index, max_value=total_trades, value=default_end_index, step=1)

                    # 4. Pine Script生成ボタン
                    st.header("4. Pine Scriptを生成")
                    if st.button("生成実行"):
                        if end_index - start_index + 1 > 200:
                            st.warning("一度に処理できるのは最大200件までです。範囲を調整してください。")
                        else:
                            # データ処理実行
                            processed_df = process_gmo_history(all_trades_df, selected_brand, start_index, end_index)

                            if not processed_df.empty:
                                st.success(f"{len(processed_df)}件の取引データを処理しました。")
                                
                                # Pine Script更新実行
                                template_path = 'trade_plotter_pinescript.txt' # 相対パスに変更
                                processed_trades_list = processed_df.to_dict(orient='records')
                                
                                final_script = update_pinescript(template_path, processed_trades_list, selected_brand)

                                if final_script:
                                    st.success("Pine Scriptの生成に成功しました。")
                                    
                                    # 結果表示とダウンロードボタン
                                    st.subheader("生成されたPine Script")
                                    st.code(final_script, language='pine')
                                    
                                    st.download_button(
                                        label="Pine Scriptをダウンロード (.txt)",
                                        data=final_script,
                                        file_name="trade_plotter_pinescript_updated.txt",
                                        mime="text/plain"
                                    )

        except Exception as e:
            st.error(f"CSVの解析中にエラーが発生しました: {e}")

# --- 公開について ---
st.info("""

**Trade Plotter for Pine Script**　概要\n
・[Trade Plotter for Pine Script]はGMOクリック証券の取引履歴からTradingViewのPineScriptで取引履歴をチャート上に表示するためのwebアプリです。\n

**使用方法**\n
0. GMOクリック証券にログインし、積算表から取引履歴(CSVファイル)をダウロードしてください。
1. [Browse files]ボタン（またはドラッグ&ドロップ）で取引履歴(CSVファイル)を選択してください。
2. チャートに表示したい銘柄を選択してください。
3. チャートに表示したい取引の範囲を選択してください。（最大200件です。)
4. [生成実行]ボタンを押してください。
5. 生成されたPine Scriptを全文コピーしてください。（Scriptの右上に[Copy to clipboard]のボタンがあります。）
6. コピーしたPine ScriptをTradingViewのPineエディタにペーストしてください。（+新規作成→インジケーターを選択→全文消去してからペーストしてください。）
7. チャートに追加ボタンを押して、しばらくおまちください。（チャートに表示されるまで時間がかかる場合があります。）
\n
**注意事項**\n
・　チャートのティッカーはGMOクリック証券の価格となるべく近いものにしてください。（米国NQ100ならNQ1!など）\n
・　チャートに追加ボタンを押してもチャートに表示されない、時間がかかりすぎる場合は取引の範囲を少なくしてください。\n
・　Le→ロングエントリー　Lg→ロング利確　Ll→ロング損切　Se→ショートエントリー　Sg→ショート利確　Sl→ショート損切を表します。\n
・　ローソク足に隠れて見にくい場合は、画面左上のインジケーターの[⋯]メニュー内の表示の順序で最前面に移動させると多少見やすくなるかもしれんません。
""")
