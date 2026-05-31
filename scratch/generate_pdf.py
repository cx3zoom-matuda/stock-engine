import os
from fpdf import FPDF
from fpdf.enums import XPos, YPos

class PresentationPDF(FPDF):
    def header(self):
        self.set_font('AppleGothic', '', 9)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, 'G20 Macro & Stock Screening Hub (trance-engine) 製品紹介資料', new_x=XPos.RIGHT, new_y=YPos.TOP, align='L')
        self.ln(10)
        self.set_draw_color(200, 200, 200)
        self.line(10, 18, 200, 18)

    def footer(self):
        self.set_y(-15)
        self.set_font('AppleGothic', '', 9)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Page {self.page_no()}', new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')

def create_pdf(output_path):
    pdf = PresentationPDF()
    
    # Find and load a valid Japanese TrueType font installed on macOS
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/NotoSansGothic-Regular.ttf",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
    ]
    
    font_loaded = False
    for path in font_paths:
        if os.path.exists(path):
            try:
                pdf.add_font("AppleGothic", "", path)
                font_loaded = True
                break
            except Exception as fe:
                continue
                
    if not font_loaded:
        raise RuntimeError("No suitable Japanese TrueType font found on this macOS system.")

    pdf.add_page()
    
    # Title
    pdf.set_font("AppleGothic", "", 18)
    pdf.set_text_color(33, 37, 41)
    pdf.multi_cell(0, 10, "製品紹介資料\nG20 Macro & Stock Screening Hub\n(trance-engine)", align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)
    
    pdf.set_font("AppleGothic", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 6, "マクロ経済と個別株評価を融合した、トップダウン型の投資意思決定支援システム。\nG20各国の経済環境を動的に捉え、最適なセクター選定と個別株の割安スクリーニングを全自動で実現します。", align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)

    # Section 1
    pdf.set_font("AppleGothic", "", 13)
    pdf.set_text_color(15, 76, 129)
    pdf.cell(0, 8, "1. 開発の背景と解決する課題", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
    pdf.ln(2)
    
    # Bullet points
    bullets = [
        ("課題1: ミクロの「ノイズ（材料・噂）」に溺れる", 
         "多くの投資家は、個別企業のニュースや噂、短期的なチャート（ミクロ情報）に気を取られ、大局的な市場トレンドを見失います。本システムはマクロ経済（金利・景気循環・原油価格）という「基準点」からアプローチすることで、大局の波に逆らわない投資を実現します。"),
        ("課題2: 個別株への「執着（バイアス）」による売り時の喪失", 
         "銘柄に惚れ込んでしまい、売り時（エグジット）を逃すのはよくある失敗です。本システムは、セクターのマクロ適合スコアが逆風に転じた瞬間を客観的に捉え、感情を排除した「売りシグナル」の基準点を提供します。"),
        ("課題3: 国ごとの「市場特性」の無視", 
         "日本株のバリュー基準（PBR 1.0倍割れなど）をそのまま米国株（ビッグテックなど）に適用すると、優良成長株がすべて「割高」と誤判定されます。本システムはG20各国の市場プロファイルに合わせた動的な基準で評価を行います。")
    ]
    for title, desc in bullets:
        pdf.set_font("AppleGothic", "", 11)
        pdf.set_text_color(15, 76, 129)
        pdf.multi_cell(0, 6, f"• {title}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
        pdf.set_font("AppleGothic", "", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(0, 5, f"   {desc}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
        pdf.ln(3)

    pdf.ln(5)

    pdf.add_page() # Page 2

    # Section 2
    pdf.set_font("AppleGothic", "", 13)
    pdf.set_text_color(15, 76, 129)
    pdf.cell(0, 8, "2. システムのコア機能", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
    pdf.ln(2)
    
    features = [
        ("G20各国の動的タブUI", "最上部にある国旗ボタンをクリックするだけで、表示されるKPI、イベント、ランキング、個別株すべてがその国のコンテキストに瞬時に切り替わります。"),
        ("マクロKPIダッシュボード", "政策金利、10年債金利、インフレ率（CPI）、景況感（PMI/短観）、GDP成長率の5大要素をFREDから並行取得して表示。"),
        ("イベント検出エンジン", "金利やインフレ等の系列データから、利上げ（rate_hike）、景気減速（business_contraction）などの汎用イベントを自動検知。"),
        ("適合スコア（ルールエンジン）", "検知されたイベントを17の主要業界セクターへ自動で翻訳・スコアリング。"),
        ("個別株バリュエーション評価", "市場プロファイルに基づいた独自のPER/PBRしきい値により、個別株の最終売買シグナル（BUY, WATCH, AVOID）を出力。"),
        ("マイ・ポートフォリオ連携", "保有する日本株・米国株のCSV（楽天証券等）をアップロードするだけで、ポートフォリオ全体のマクロ適合加重スコアや評価額・損益を全自動で算出・レポート化。")
    ]
    for title, desc in features:
        pdf.set_font("AppleGothic", "", 10)
        pdf.set_text_color(30, 30, 30)
        pdf.multi_cell(0, 5, f"■ {title}: {desc}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
        pdf.ln(2)

    pdf.ln(5)

    # Section 3: Competitive Analysis Table
    pdf.set_font("AppleGothic", "", 13)
    pdf.set_text_color(15, 76, 129)
    pdf.cell(0, 8, "3. 主要競合ツールとの機能比較", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
    pdf.ln(4)
    
    # Table dimensions
    col_width_features = 50
    col_width_others = 35
    row_height = 8
    
    # Header
    pdf.set_font("AppleGothic", "", 9)
    pdf.set_fill_color(15, 76, 129)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(col_width_features, row_height, "機能・特徴", 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=True)
    pdf.cell(col_width_others, row_height, "本システム", 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=True)
    pdf.cell(col_width_others, row_height, "Koyfin/TV", 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=True)
    pdf.cell(col_width_others, row_height, "Macrobond/TE", 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=True)
    pdf.cell(col_width_others, row_height, "Bloomberg", 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C', fill=True)
    
    # Data Rows
    pdf.set_text_color(50, 50, 50)
    pdf.set_fill_color(240, 244, 248)
    
    rows = [
        ("マクロデータの可視化", "○ (FRED同期)", "○ (高度)", "◎ (専門的)", "◎ (圧倒的)"),
        ("個別株財務の表示", "○ (yfinance)", "○ (高度)", "× (未対応)", "◎ (圧倒的)"),
        ("マクロから業界への翻訳", "◎ (全自動)", "× (表示のみ)", "× (表示のみ)", "× (要自作)"),
        ("自動投資判断 (BUY/WATCH)", "◎ (市場別しきい値)", "× (表示のみ)", "× (未対応)", "× (要自作)"),
        ("定性シグナル(手動)", "◎ (ワンクリック)", "× (未対応)", "× (未対応)", "× (要自作)"),
        ("保有株マクロ分析", "◎ (楽天証券対応)", "× (未対応)", "× (未対応)", "× (要自作)"),
        ("年間利用コスト", "月$50想定 (年9万)", "数万〜十数万円", "数十万円", "約300万〜400万")
    ]
    
    fill = False
    for r in rows:
        pdf.cell(col_width_features, row_height, r[0], 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L', fill=fill)
        pdf.cell(col_width_others, row_height, r[1], 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=fill)
        pdf.cell(col_width_others, row_height, r[2], 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=fill)
        pdf.cell(col_width_others, row_height, r[3], 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=fill)
        pdf.cell(col_width_others, row_height, r[4], 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C', fill=fill)
        fill = not fill
        
    pdf.ln(8)

    pdf.add_page() # Page 3

    # Section 4
    pdf.set_font("AppleGothic", "", 13)
    pdf.set_text_color(15, 76, 129)
    pdf.cell(0, 8, "4. 本システムの独自優位性 (USP)", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
    pdf.ln(2)
    
    usps = [
        ("① 「データ表示」ではなく「意思決定ロジック」を内包", 
         "既存の多くのツールは「ビューアー」ですが、本システムは「マクロから個別株評価への意思決定」ロジックをコード内に所有。月額50ドル想定という手の届く価格でありながら、数百万円規模のプロ向け端末と同等以上の意思決定フローを提供し、投資バイアスを排除します。"),
        ("② ストレスシミュレーション（手動上書き）機能", 
         "サイドバー of 「Qualitative & Regional Triggers」を使えば、「仮にこれから中央銀行が急激な利上げ（rate_hike）を行った場合、自分のポートフォリオはどうなるか」を事前にダッシュボード上でシミュレーションし、先手を打ったエグジット・アロケーション計画が立てられます。"),
        ("③ プラグイン構造による高い拡張性", 
         "データ取得層（マクロプロバイダー、個別株プロバイダー）をプラグイン構造として抽象化しているため、将来的なAPIの仕様変更や別のベンダー（日銀直接APIなど）への切り替えも、コアロジックを一切汚さずに迅速に対応可能です。")
    ]
    for title, desc in usps:
        pdf.set_font("AppleGothic", "", 11)
        pdf.set_text_color(15, 76, 129)
        pdf.multi_cell(0, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
        pdf.set_font("AppleGothic", "", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(0, 5, desc, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
        pdf.ln(4)
        
    pdf.ln(4)

    # Section 5
    pdf.set_font("AppleGothic", "", 13)
    pdf.set_text_color(15, 76, 129)
    pdf.cell(0, 8, "5. 製品化へ向けた開発ロードマップ（プレミアム機能案）", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
    pdf.ln(2)
    
    roadmap = [
        ("① マイ・ポートフォリオのマルチ証券会社対応", 
         "現在対応している楽天証券に加え、SBI証券やInteractive Brokers等、主要各社の異なるCSVエクスポート自動パースに標準対応。インポート不統一を吸収する手動UI編集機能も拡張します。"),
        ("② マクロアロケーション自動最適化（リバランス提案）", 
         "現在の保有ポートフォリオに対して、検知されたマクロサイクル（利上げ・景気減速など）に最も適合し、リスクを最小化するような「セクターリバランス案」を全自動で生成・推薦します。"),
        ("③ ポートフォリオ・マクロアラートの高度化", 
         "保有株のマクロ適合スコアが一定基準を下回った際、自動でプッシュ通知や詳細なリスク原因分析レポート（PDF）を出力し、メール等へ配信する機能。")
    ]
    for r_title, r_desc in roadmap:
        pdf.set_font("AppleGothic", "", 11)
        pdf.set_text_color(15, 76, 129)
        pdf.multi_cell(0, 6, r_title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
        pdf.set_font("AppleGothic", "", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(0, 5, r_desc, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
        pdf.ln(4)
        
    pdf.output(output_path)

if __name__ == "__main__":
    os.makedirs("scratch", exist_ok=True)
    create_pdf("scratch/product_presentation.pdf")
    print("Successfully generated scratch/product_presentation.pdf")
