import json
import re

def update_pinescript(pinescript_template_path, json_path, output_pinescript_path):
    with open(pinescript_template_path, 'r', encoding='utf-8') as f:
        pinescript_content = f.read()

    with open(json_path, 'r', encoding='utf-8') as f:
        processed_trades = json.load(f)

    if not processed_trades:
        print("処理された取引履歴データがありません。")
        return

    # Find the start and end of the template block
    start_marker = '//trade1'
    end_marker = '//trade1_fin'

    start_index = pinescript_content.find(start_marker)
    end_index = pinescript_content.find(end_marker)

    if start_index == -1 or end_index == -1:
        print(f"エラー: '{start_marker}' または '{end_marker}' マーカーが見つかりません。")
        return

    # Adjust end_index to include the end_marker itself
    end_index += len(end_marker)

    # Extract the template block
    trade_block_template = pinescript_content[start_index:end_index]

    # Extract parts of the content
    content_before_template = pinescript_content[:start_index]
    content_after_template = pinescript_content[end_index:]

    generated_trade_blocks = []
    for i, trade_data in enumerate(processed_trades[:100]): # 最大100件まで処理
        trade_num = i + 1
        current_trade_block = trade_block_template

        # Replace 'trade1' with 'tradeX'
        current_trade_block = current_trade_block.replace(f'trade1', f'trade{trade_num}')

        # Replace <1A> with <XA> and <1B> with <XB>
        current_trade_block = current_trade_block.replace(f'<1A>', f'<{trade_num}A>')
        current_trade_block = current_trade_block.replace(f'<1B>', f'<{trade_num}B>')

        # Replace <XA> and <XB> with actual values
        current_trade_block = current_trade_block.replace(f'<{trade_num}A>', trade_data['PineTimestamp'])
        current_trade_block = current_trade_block.replace(f'<{trade_num}B>', trade_data['TradeCategory'])

        generated_trade_blocks.append(current_trade_block)

    # Reconstruct the final content
    final_pinescript_content = (
        content_before_template +
        '\n'.join(generated_trade_blocks) +
        content_after_template
    )

    with open(output_pinescript_path, 'w', encoding='utf-8') as f:
        f.write(final_pinescript_content)

    print(f"{output_pinescript_path} を作成しました。")

if __name__ == '__main__':
    pinescript_template_file = r'C:\Users\harunami\Desktop\gemini_study\tradeploter_for_pine\trade_plotter_pinescript.txt'
    json_file = r'C:\Users\harunami\Desktop\gemini_study\tradeploter_for_pine\processed_trades.json'
    output_file = r'C:\Users\harunami\Desktop\gemini_study\tradeploter_for_pine\trade_plotter_pinescript_updated.txt'
    update_pinescript(pinescript_template_file, json_file, output_file)
