PER_OUTPUT = """根據以下任務資訊，針對每個「工作產出」分別生成對應的行為指標，並同步自評品質。

任務名稱：{task_name}
情境（When/Where）：{situation}
目的（Why）：{purpose}
協作對象（Who）：{collaborators}
服務對象：{stakeholders}
工具/方法（How）：{tools}
動作步驟（How to）：{workflow_steps}
品質標準：{quality_standards}
時效標準：{time_standards}
STAR 真實案例：{star_case}
{icap_ref_section}
工作產出清單（每項需生成獨立指標）：
{outputs_numbered}

請針對每個產出輸出一個行為指標（JSON 陣列，只輸出 JSON）：
[
  {{
    "output_name": "產出名稱（與清單中完全一致）",
    "indicator_5w2h": "在【情境】下，為了【目的】，與【協作對象】協作，使用【工具】完成【動作步驟】，產出【此具體產出物】，達到【品質/時效標準】。",
    "indicator_abcd": "面對【對象】，能【行為動詞+動作】，在【工具/條件】下，產出【產出物】，達到【標準】。",
    "quality_dims": {{
      "has_situation": true,
      "has_purpose": true,
      "has_collaborators": true,
      "has_tools": true,
      "has_action": true,
      "has_output": true,
      "has_standard": true
    }}
  }}
]

規則：
- output_name 必須與清單中的產出名稱完全一致，不要改寫
- 每個指標必須在 indicator_5w2h 中明確提及對應的產出物
- 使用工作者真實描述的工具名稱（ERP、Excel 等），不使用「相關工具」
- 不使用「負責、協助、處理」等抽象動詞，改用具體可觀察動作
- 不得加入任務資訊中沒有出現的服務對象、工具、產出或品質標準
{icap_ref_rule}"""

SINGLE = """根據以下任務資訊，生成企業情境化行為指標，並同步自評品質。

任務名稱：{task_name}
When/Where（情境）：{situation}
Why（目的）：{purpose}
Who/協作對象：{collaborators}
Who/服務對象：{stakeholders}
How（工具/方法）：{tools}
What（動作步驟）：{workflow_steps}
品質標準：{quality_standards}
時效標準：{time_standards}
STAR 真實案例：{star_case}
{icap_ref_section}
輸出 JSON（只輸出 JSON）：
{{
  "indicator_5w2h": "在【情境】下，為了【目的】，與【協作對象】協作，使用【工具】完成【動作】，達成【品質/時效標準】。",
  "indicator_abcd": "面對【對象】，能【行為動詞+具體動作】，在【條件/工具】下，達到【品質/數量/時效】標準。",
  "quality_dims": {{
    "has_situation": true,
    "has_purpose": true,
    "has_collaborators": true,
    "has_tools": true,
    "has_action": true,
    "has_output": true,
    "has_standard": true
  }}
}}

規則：
- 若有 iCAP 參考指標，只能參考措辭風格；不得直接複製
- 不得加入任務資訊中沒有出現的服務對象、工具、產出或品質標準
- 使用工作者真實描述的工具名稱，不使用「相關工具」
- 不使用「負責、協助、處理」等抽象動詞，改用具體可觀察動作
"""
