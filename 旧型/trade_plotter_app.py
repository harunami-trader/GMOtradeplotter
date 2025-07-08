# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
import pytz
import json
import re
import os

# convert_encoding.py の内容を関数として統合
def convert_encoding(input_file_path, output_file_path):
    try:
        with open(input_file_path, 'rb') as f_in:
            content = f_in.read()

        # 検出可能なエンコーディングのリスト
        encodings = ['shift_jis', 'cp932', 'euc_jp', 'utf-8']
        decoded_content = None
        detected_encoding = None

        for enc in encodings:
            try:
                decoded_content = content.decode(enc)
                detected_encoding = enc
                break
            except UnicodeDecodeError:
                continue

        if decoded_content is None:
            raise UnicodeDecodeError("decode_error", b'', 0, 0, "適切なエンコーディングを検出できませんでした。")

        with open(output_file_path, 'w', encoding='utf-8', newline='') as f_out:
            f_out.write(decoded_content)
        return True
    except Exception as e:
        messagebox.showerror("エンコーディングエラー", f"ファイルのエンコーディング変換中にエラーが発生しました: {e}")
        return False

# process_gmo_history.py の内容を関数として統合
def process_gmo_history(file_path, selected_brand, start_trade_index, end_trade_index):
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')

        # 米国NQ100ミニの取引履歴を抽出
        nq100_df = df[df['銘柄名'] == selected_brand].copy()

        if nq100_df.empty:
            messagebox.showinfo("情報", f"{selected_brand} の取引履歴が見つかりませんでした。")
            return pd.DataFrame()

        # 必要な列を抽出
        # 列名が環境によって文字化けする可能性を考慮し、動的に取得
        col_約定日時 = [col for col in df.columns if '約定日時' in col][0]
        col_取引区分 = [col for col in df.columns if '取引区分' in col][0]
        col_売買区分 = [col for col in df.columns if '売買区分' in col][0]
        col_約定単価 = [col for col in df.columns if '約定単価' in col][0]
        col_実現損益 = [col for col in df.columns if '実現損益' in col][0]

        nq100_df = nq100_df[[col_約定日時, col_取引区分, col_売買区分, col_約定単価, col_実現損益]]

        # 約定日時をdatetime型に変換し、タイムゾーンを考慮 (JST)
        jst = pytz.timezone('Asia/Tokyo')
        nq100_df[col_約定日時] = pd.to_datetime(nq100_df[col_約定日時]).dt.tz_localize(jst, ambiguous='infer')

        # timestamp("GMT+9", year, month, day, hour, minute, second) 形式の文字列を生成
        nq100_df['PineTimestamp'] = nq100_df[col_約定日時].apply(
            lambda x: f'timestamp("GMT+9", {x.year}, {x.month}, {x.day}, {x.hour}, {x.minute}, {x.second})'
        )

        # 取引に連番のIDを付与
        nq100_df['TradeID'] = [f'trade{i+1}' for i in range(len(nq100_df))]

        # 「実現損益（円貨）」を数値型に変換
        nq100_df[col_実現損益] = pd.to_numeric(nq100_df[col_実現損益], errors='coerce')

        # TradeCategoryを付与
        def get_trade_category(row):
            if row[col_取引区分] == 'CFD新規':
                if row[col_売買区分] == '買':
                    return 'Le'
                elif row[col_売買区分] == '売':
                    return 'Se'
            elif row[col_取引区分] in ['CFD決済', 'CFDロスカット']:
                if row[col_売買区分] == '売': # 決済売りはLongの決済
                    if row[col_実現損益] >= 0:
                        return 'Lg'
                    else:
                        return 'Ll'
                elif row[col_売買区分] == '買': # 決済買いはShortの決済
                    if row[col_実現損益] >= 0:
                        return 'Sg'
                    else:
                        return 'Sl'
            return 'Unknown'

        nq100_df['TradeCategory'] = nq100_df.apply(get_trade_category, axis=1)

        # ユーザーが選択した範囲でデータを抽出
        processed_df = nq100_df.iloc[start_trade_index-1:end_trade_index] # -1 because index is 0-based

        return processed_df

    except FileNotFoundError:
        messagebox.showerror("エラー", f"ファイルが見つかりません - {file_path}")
        return pd.DataFrame()
    except Exception as e:
        messagebox.showerror("エラー", f"データの処理中にエラーが発生しました: {e}")
        return pd.DataFrame()

# update_pinescript.py の内容を関数として統合
def update_pinescript(pinescript_template_path, processed_trades_data, output_pinescript_path):
    try:
        with open(pinescript_template_path, 'r', encoding='utf-8') as f:
            pinescript_content = f.read()

        if not processed_trades_data:
            messagebox.showinfo("情報", "処理された取引履歴データがありません。Pine Scriptは生成されません。")
            return False

        start_marker = '//trade1'
        end_marker = '//trade1_fin'

        start_index = pinescript_content.find(start_marker)
        end_index = pinescript_content.find(end_marker)

        if start_index == -1 or end_index == -1:
            messagebox.showerror("エラー", f"Pine Scriptテンプレートに '{start_marker}' または '{end_marker}' マーカーが見つかりません。")
            return False

        end_index += len(end_marker)

        trade_block_template = pinescript_content[start_index:end_index]

        content_before_template = pinescript_content[:start_index]
        content_after_template = pinescript_content[end_index:]

        generated_trade_blocks = []
        # 約定単価の列名を動的に取得するためのキー（最初のデータから推測）
        price_key = [key for key in processed_trades_data[0].keys() if '約定単価' in key][0]

        for i, trade_data in enumerate(processed_trades_data):
            trade_num = i + 1
            current_trade_block = trade_block_template

            current_trade_block = current_trade_block.replace(f'trade1', f'trade{trade_num}')
            current_trade_block = current_trade_block.replace(f'<1A>', f'<{trade_num}A>')
            current_trade_block = current_trade_block.replace(f'<1B>', f'<{trade_num}B>')
            current_trade_block = current_trade_block.replace(f'<1C>', f'<{trade_num}C>')

            current_trade_block = current_trade_block.replace(f'<{trade_num}A>', trade_data['PineTimestamp'])
            current_trade_block = current_trade_block.replace(f'<{trade_num}B>', trade_data['TradeCategory'])
            current_trade_block = current_trade_block.replace(f'<{trade_num}C>', str(trade_data[price_key]))

            generated_trade_blocks.append(current_trade_block)

        final_pinescript_content = (
            content_before_template +
            '\n'.join(generated_trade_blocks) +
            content_after_template
        )

        with open(output_pinescript_path, 'w', encoding='utf-8') as f:
            f.write(final_pinescript_content)

        return True
    except Exception as e:
        messagebox.showerror("Pine Script生成エラー", f"Pine Scriptの生成中にエラーが発生しました: {e}")
        return False

class TradePlotterApp:
    def __init__(self, master):
        self.master = master
        master.title("Trade Plotter App")

        self.csv_file_path = tk.StringVar()
        self.selected_brand = tk.StringVar()
        self.all_trades_df = pd.DataFrame() # 全取引データを保持するDataFrame

        # CSVファイル選択フレーム
        self.file_frame = tk.LabelFrame(master, text="1. CSVファイル選択")
        self.file_frame.pack(padx=10, pady=10, fill="x")

        self.file_label = tk.Label(self.file_frame, text="選択されたファイル:")
        self.file_label.pack(side="left", padx=5, pady=5)

        self.file_entry = tk.Entry(self.file_frame, textvariable=self.csv_file_path, width=50, state="readonly")
        self.file_entry.pack(side="left", padx=5, pady=5, expand=True, fill="x")

        self.browse_button = tk.Button(self.file_frame, text="参照", command=self.browse_csv_file)
        self.browse_button.pack(side="left", padx=5, pady=5)

        # 銘柄選択フレーム
        self.brand_frame = tk.LabelFrame(master, text="2. 銘柄選択")
        self.brand_frame.pack(padx=10, pady=10, fill="x")

        self.brand_label = tk.Label(self.brand_frame, text="銘柄名:")
        self.brand_label.pack(side="left", padx=5, pady=5)

        self.brand_option_menu = tk.OptionMenu(self.brand_frame, self.selected_brand, "")
        self.brand_option_menu.pack(side="left", padx=5, pady=5, expand=True, fill="x")
        self.brand_option_menu.config(state="disabled")
        self.selected_brand.trace_add('write', self.on_brand_selected)

        # 取引範囲選択フレーム
        self.trade_range_frame = tk.LabelFrame(master, text="3. 取引範囲選択 (最大200件)")
        self.trade_range_frame.pack(padx=10, pady=10, fill="x")

        self.total_trades_label = tk.Label(self.trade_range_frame, text="総取引数: 0")
        self.total_trades_label.pack(padx=5, pady=5)

        self.from_label = tk.Label(self.trade_range_frame, text="From:")
        self.from_label.pack(side="left", padx=5, pady=5)
        self.from_entry = tk.Entry(self.trade_range_frame, width=10)
        self.from_entry.pack(side="left", padx=5, pady=5)
        self.from_entry.insert(0, "1")

        self.to_label = tk.Label(self.trade_range_frame, text="To:")
        self.to_label.pack(side="left", padx=5, pady=5)
        self.to_entry = tk.Entry(self.trade_range_frame, width=10)
        self.to_entry.pack(side="left", padx=5, pady=5)
        self.to_entry.insert(0, "200")

        # 処理実行ボタン
        self.process_button = tk.Button(master, text="4. Pine Script生成", command=self.process_data)
        self.process_button.pack(padx=10, pady=10)

    def browse_csv_file(self):
        file_path = filedialog.askopenfilename(
            title="取引履歴CSVファイルを選択",
            filetypes=[("CSVファイル", "*.csv")]
        )
        if file_path:
            self.csv_file_path.set(file_path)
            self.load_and_process_csv()

    def load_and_process_csv(self):
        input_path = self.csv_file_path.get()
        if not input_path:
            return

        # 一時的な変換済みファイルパス
        temp_converted_path = os.path.join(os.path.dirname(input_path), "temp_converted_gmo_history.csv")

        if not convert_encoding(input_path, temp_converted_path):
            return

        try:
            # 全銘柄のデータを読み込み、銘柄名を抽出
            df = pd.read_csv(temp_converted_path, encoding='utf-8')
            if '銘柄名' not in df.columns:
                messagebox.showerror("エラー", "CSVファイルに '銘柄名' カラムが見つかりません。")
                return

            unique_brands = df['銘柄名'].unique().tolist()
            if not unique_brands:
                messagebox.showinfo("情報", "CSVファイルから銘柄名が抽出できませんでした。")
                return

            # OptionMenuを更新
            self.brand_option_menu['menu'].delete(0, 'end')
            for brand in unique_brands:
                self.brand_option_menu['menu'].add_command(label=brand, command=tk._setit(self.selected_brand, brand))
            self.brand_option_menu.config(state="normal")
            self.selected_brand.set(unique_brands[0]) # 最初の銘柄をデフォルトで選択

            # 全取引データを保持
            self.all_trades_df = df

        except Exception as e:
            messagebox.showerror("CSV読み込みエラー", f"CSVファイルの読み込みまたは解析中にエラーが発生しました: {e}")
        finally:
            # 一時ファイルを削除
            if os.path.exists(temp_converted_path):
                os.remove(temp_converted_path)

    def on_brand_selected(self, *args):
        selected_brand = self.selected_brand.get()
        if not selected_brand or self.all_trades_df.empty:
            self.total_trades_label.config(text="総取引数: 0")
            return

        # 選択された銘柄の取引数を更新
        filtered_df = self.all_trades_df[self.all_trades_df['銘柄名'] == selected_brand]
        self.total_trades_label.config(text=f"総取引数: {len(filtered_df)}")
        self.to_entry.delete(0, tk.END)
        self.to_entry.insert(0, str(min(len(filtered_df), 200))) # 最大200件まで

    def process_data(self):
        csv_path = self.csv_file_path.get()
        selected_brand = self.selected_brand.get()
        if not csv_path or not selected_brand:
            messagebox.showwarning("警告", "CSVファイルと銘柄名を選択してください。")
            return

        try:
            start_index = int(self.from_entry.get())
            end_index = int(self.to_entry.get())
            if not (1 <= start_index <= end_index and end_index - start_index + 1 <= 200):
                messagebox.showwarning("警告", "取引範囲は1から始まり、終了が開始以上で、最大200件までです。")
                return

        except ValueError:
            messagebox.showwarning("警告", "取引範囲は数値を入力してください。")
            return

        # 一時的な変換済みファイルパス
        temp_converted_path = os.path.join(os.path.dirname(csv_path), "temp_converted_gmo_history.csv")
        if not convert_encoding(csv_path, temp_converted_path):
            return

        # process_gmo_history のロジックを実行
        processed_df = process_gmo_history(temp_converted_path, selected_brand, start_index, end_index)
        if processed_df.empty:
            return

        # processed_trades.json として保存
        output_json_path = os.path.join(os.path.dirname(csv_path), "processed_trades.json")
        processed_df.to_json(output_json_path, orient='records', indent=4, force_ascii=False)
        messagebox.showinfo("成功", f"処理された取引履歴を {output_json_path} に保存しました。")

        # update_pinescript のロジックを実行
        pinescript_template_file = r'C:\Users\harunami\Desktop\gemini_study\tradeploter_for_pine\trade_plotter_pinescript.txt'
        output_pinescript_file = os.path.join(os.path.dirname(csv_path), "trade_plotter_pinescript_updated.txt")

        # DataFrameをJSON形式のリストに変換して渡す
        processed_trades_list = processed_df.to_dict(orient='records')

        if update_pinescript(pinescript_template_file, processed_trades_list, output_pinescript_file):
            messagebox.showinfo("成功", f"Pine Scriptを {output_pinescript_file} に生成しました。")
        else:
            messagebox.showerror("エラー", "Pine Scriptの生成に失敗しました。")

        # 一時ファイルを削除
        if os.path.exists(temp_converted_path):
            os.remove(temp_converted_path)


root = tk.Tk()
app = TradePlotterApp(root)
root.mainloop()
