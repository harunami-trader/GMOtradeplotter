import codecs

input_file = r'C:\Users\harunami\Desktop\gemini_study\tradeploter_for_pine\gmo_history.csv'
output_file = r'C:\Users\harunami\Desktop\gemini_study\tradeploter_for_pine\gmo_history_converted.csv'
input_encoding = 'cp932'
output_encoding = 'utf-8-sig'

try:
    with codecs.open(input_file, 'r', encoding=input_encoding) as infile:
        content = infile.read()
    with codecs.open(output_file, 'w', encoding=output_encoding) as outfile:
        outfile.write(content)
    print(f"'{input_file}' を '{output_file}' に '{output_encoding}' エンコーディングで変換しました。")
except UnicodeDecodeError as e:
    print(f"デコードエラーが発生しました: {e}")
    print(f"'{input_file}' は '{input_encoding}' で正しく読み込めない可能性があります。")
except Exception as e:
    print(f"エラーが発生しました: {e}")