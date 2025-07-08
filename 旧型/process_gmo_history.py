import pandas as pd
import pytz # Add this import

def process_gmo_history(file_path):
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')

        # 米国NQ100ミニの取引履歴を抽出
        nq100_df = df[df['銘柄名'] == '米国NQ100ミニ'].copy()

        if nq100_df.empty:
            print("米国NQ100ミニの取引履歴が見つかりませんでした。")
            return pd.DataFrame()

        # 必要な列を抽出（「実現損益（円換算額）」を追加）
        nq100_df = nq100_df[['約定日時', '取引区分', '売買区分', '約定単価', '実現損益（円貨）']]

        # 約定日時をdatetime型に変換し、タイムゾーンを考慮
        # Assuming the timestamps in the CSV are in JST (Japan Standard Time)
        jst = pytz.timezone('Asia/Tokyo')
        nq100_df['約定日時'] = pd.to_datetime(nq100_df['約定日時']).dt.tz_localize(jst, ambiguous='infer')
        # timestamp("GMT+9", year, month, day, hour, minute, second) 形式の文字列を生成
        nq100_df['PineTimestamp'] = nq100_df['約定日時'].apply(
            lambda x: f'timestamp("GMT+9", {x.year}, {x.month}, {x.day}, {x.hour}, {x.minute}, {x.second})'
        )

        # 取引に連番のIDを付与
        nq100_df['TradeID'] = [f'trade{i+1}' for i in range(len(nq100_df))]

        # 「実現損益（円貨）」を数値型に変換
        nq100_df['実現損益（円貨）'] = pd.to_numeric(nq100_df['実現損益（円貨）'], errors='coerce')

        # TradeCategoryを付与
        def get_trade_category(row):
            if row['取引区分'] == 'CFD新規':
                if row['売買区分'] == '買':
                    return 'Le'
                elif row['売買区分'] == '売':
                    return 'Se'
            elif row['取引区分'] in ['CFD決済', 'CFDロスカット']:
                if row['売買区分'] == '売': # 決済売りはLongの決済
                    if row['実現損益（円貨）'] >= 0:
                        return 'Lg'
                    else:
                        return 'Ll'
                elif row['売買区分'] == '買': # 決済買いはShortの決済
                    if row['実現損益（円貨）'] >= 0:
                        return 'Sg'
                    else:
                        return 'Sl'
            return 'Unknown' # 上記のいずれにも該当しない場合

        nq100_df['TradeCategory'] = nq100_df.apply(get_trade_category, axis=1)

        print("米国NQ100ミニの取引履歴を抽出・整形しました。")
        return nq100_df

    except FileNotFoundError:
        print(f"エラー: ファイルが見つかりません - {file_path}")
        return pd.DataFrame()
    except Exception as e:
        print(f"データの処理中にエラーが発生しました: {e}")
        return pd.DataFrame()

if __name__ == '__main__':
    input_csv_path = r'C:\Users\harunami\Desktop\gemini_study\tradeploter_for_pine\gmo_history_converted.csv'
    nq100_trades = process_gmo_history(input_csv_path)

    if not nq100_trades.empty:
        # 処理結果をJSONファイルとして保存
        output_json_path = r'C:\Users\harunami\Desktop\gemini_study\tradeploter_for_pine\processed_trades.json'
        nq100_trades.to_json(output_json_path, orient='records', indent=4, force_ascii=False)
        print(f"\n処理された取引履歴を {output_json_path} に保存しました。")
        # print("\n抽出された米国NQ100ミニの取引履歴（全件）:")
        # print(nq100_trades.to_string())