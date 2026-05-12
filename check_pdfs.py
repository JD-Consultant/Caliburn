import pdfplumber

pdf_files = [
    r'data/電腦周邊設備硬體研發工程人員-職能基準.pdf',
    r'data/店面智慧化設計人員-職能基準.pdf'
]

target_headers = ['工作任務', '工作產出', '行為指標', '職能級別', '知識', '技能']

for pdf_path in pdf_files:
    print(f'\n--- Analyzing: {pdf_path} ---')
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                if not tables:
                    continue
                
                print(f'Page {i+1}: Found {len(tables)} tables')
                for table_idx, table in enumerate(tables):
                    # Filter out empty or None rows
                    rows = [row for row in table if any(row)]
                    if not rows:
                        continue
                    
                    print(f'  Table {table_idx+1}: {len(rows)} rows')
                    for row in rows[:3]:
                        condensed = [str(cell).replace("\n", " ")[:20] for cell in row if cell is not None]
                        print(f'    Row (len {len(row)}): {condensed}')
                    
                    # Check for candidate header
                    flattened_table = [str(cell) for row in rows for cell in row if cell]
                    found_headers = [h for h in target_headers if any(h in cell for cell in flattened_table)]
                    if found_headers:
                        print(f'    -> Candidate OCU content table! Found headers: {found_headers}')

    except Exception as e:
        print(f'Error processing {pdf_path}: {e}')
