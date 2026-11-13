import os
import pypdf
import re

# =========================================================================
# AUTOMATED SOLAR AUDIT PARSER & INJECTOR SCRIPT
# Vykon Indus Technologies
# =========================================================================

workspace_dir = "e:\\vykon"
html_path = os.path.join(workspace_dir, "index.html")

print("Scanning workspace for utility bills...")
pdf_files = [f for f in os.listdir(workspace_dir) if f.endswith(".pdf")]

# Lucknow average daily peak sun hours by month (Jan-Dec)
lucknow_peak_sun_hours = [3.8, 4.5, 5.2, 5.8, 6.0, 5.0, 3.8, 3.6, 4.2, 4.8, 4.2, 3.5]
month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

parsed_bills = []

for file in pdf_files:
    # Skip non-bill PDFs
    if "handout" in file.lower() or "success" in file.lower():
        continue
        
    path = os.path.join(workspace_dir, file)
    try:
        reader = pypdf.PdfReader(path)
        text = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
        
        # Extract fields
        bill_date_m = re.search(r'Bill Date\s*([0-9A-Za-z-]+)', text, re.IGNORECASE)
        acct_m = re.search(r'Account (?:No\.|সং\.)\s*:\s*([0-9-]+)', text, re.IGNORECASE)
        bill_num_m = re.search(r'Bill Number\s*:\s*([0-9-]+)', text, re.IGNORECASE)
        units_m = re.search(r'Net Billed Unit\s*([0-9.]+)', text, re.IGNORECASE)
        payable_m = re.search(r'Payable Amount\s*([0-9]+)', text, re.IGNORECASE)
        meter_type_m = re.search(r'Meter Type\s*:\s*(\w+)', text, re.IGNORECASE)
        
        if not bill_date_m:
            continue
            
        bdate_str = bill_date_m.group(1)
        acct = acct_m.group(1) if acct_m else "0279991255"
        bnum = bill_num_m.group(1) if bill_num_m else "N/A"
        units = float(units_m.group(1)) if units_m else 0.0
        payable = float(payable_m.group(1)) if payable_m else 0.0
        mtype = meter_type_m.group(1) if meter_type_m else "POSTPAID"
        
        # Parse month and year from Date string (e.g. 09-OCT-2024 or 21-MAY-2026)
        date_parts = bdate_str.split('-')
        month_str = date_parts[1].capitalize() if len(date_parts) > 1 else "Jan"
        year_str = date_parts[2] if len(date_parts) > 2 else "2025"
        
        month_idx = 1
        for idx, name in enumerate(month_names):
            if name.lower() == month_str.lower():
                month_idx = idx + 1
                break
                
        # Classification Rule:
        # Check if the filename or the text content contains "sha" or "145632"
        # Or if the meter type is GEN_NETBILL (solar fallback)
        is_solar = False
        if ("sha" in file.lower() or "145632" in file or 
            "sha" in text.lower() or "145632" in text or 
            mtype.upper() == "GEN_NETBILL"):
            is_solar = True
            
        parsed_bills.append({
            "file": file,
            "month_idx": month_idx,
            "month_name": month_str,
            "year": year_str,
            "bill": payable,
            "kwh": units,
            "is_solar": is_solar,
            "acct": acct
        })
        
    except Exception as e:
        print(f"Error parsing {file}: {e}")

# Sort chronologically by year and then month index
parsed_bills.sort(key=lambda x: (int(x["year"]), x["month_idx"]))

print(f"\nSuccessfully parsed {len(parsed_bills)} bills:")
for b in parsed_bills:
    status = "Solar Active" if b["is_solar"] else "Grid Only"
    print(f" - {b['month_name']} {b['year']}: Bill=Rs.{b['bill']:.0f}, kWh={b['kwh']:.0f} ({status})")

# =========================================================================
# MODEL TRAINING & CALIBRATION (Python Verification)
# =========================================================================
non_solar_bills = [b for b in parsed_bills if not b["is_solar"]]
solar_bills = [b for b in parsed_bills if b["is_solar"]]

# Linear Regression helper
def fit_linear_regression(x, y):
    n = len(x)
    if n == 0:
        return 0, 0
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xx = sum(val * val for val in x)
    sum_xy = sum(x[i] * y[i] for i in range(n))
    denominator = (n * sum_xx - sum_x * sum_x)
    if denominator == 0:
        return 0, sum_y / n
    slope = (n * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept

# Fit baseline trend
x_idx = [b["month_idx"] for b in non_solar_bills]
y_kwh = [b["kwh"] for b in non_solar_bills]
y_bill = [b["bill"] for b in non_solar_bills]

slope_kwh, intercept_kwh = fit_linear_regression(x_idx, y_kwh)
slope_bill, intercept_bill = fit_linear_regression(x_idx, y_bill)

print(f"\nTrained Model Baseline Parameters:")
print(f" - kWh Trend: kWh = {slope_kwh:.2f} * Month + {intercept_kwh:.2f}")
print(f" - Bill Trend: Bill = Rs.{slope_bill:.2f} * Month + Rs.{intercept_bill:.2f}")

# System Efficiency Calibration
solar_capacity_kw = 45.0  # From PDF Sanction Load: 45 kW
efficiencies = []

for b in solar_bills:
    pred_base_kwh = slope_kwh * b["month_idx"] + intercept_kwh
    act_grid_kwh = b["kwh"]
    observed_contribution = pred_base_kwh - act_grid_kwh
    
    peak_hours = lucknow_peak_sun_hours[b["month_idx"] - 1]
    theoretical_gen_factor = solar_capacity_kw * peak_hours * 30
    eta = observed_contribution / theoretical_gen_factor if theoretical_gen_factor != 0 else 0
    efficiencies.append(eta)
    print(f"Calibrating on {b['month_name']} {b['year']}: Computed Efficiency = {eta*100:.1f}%")

avg_efficiency = sum(efficiencies)/len(efficiencies) if efficiencies else 0.75
print(f"Calibrated System Efficiency (eta): {avg_efficiency*100:.2f}%")

# =========================================================================
# HTML AUTOMATED INJECTION
# =========================================================================
if os.path.exists(html_path):
    print(f"\nInjecting parsed bill data into index.html...")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    # Generate 12 rows of HTML inputs based on our parsed bills
    # If we have less than 12 bills, we backfill or pad with predictions
    table_rows_html = ""
    js_sample_bills = []
    js_sample_kwh = []
    js_sample_solar = []
    
    # We map Dec (Month 1) to Nov (Month 12)
    original_month_names = [
        "Month 1 (Dec)",
        "Month 2 (Jan)",
        "Month 3 (Feb)",
        "Month 4 (Mar)",
        "Month 5 (Apr)",
        "Month 6 (May)",
        "Month 7 (Jun)",
        "Month 8 (Jul)",
        "Month 9 (Aug)",
        "Month 10 (Sep)",
        "Month 11 (Oct)",
        "Month 12 (Nov)"
    ]
    for m_idx in range(1, 13):
        m_label = original_month_names[m_idx - 1]
        # Map Table Month index (1=Dec, 2=Jan, ..., 12=Nov) to Calendar Month index (12=Dec, 1=Jan, ..., 11=Nov)
        cal_month_idx = 12 if m_idx == 1 else m_idx - 1
        
        # Find if we have a parsed bill for this month (preferring latest year)
        matching_bill = None
        for b in reversed(parsed_bills):
            if b["month_idx"] == cal_month_idx:
                matching_bill = b
                break
                
        if matching_bill:
            bill_val = int(matching_bill["bill"])
            kwh_val = int(matching_bill["kwh"])
            is_sol = matching_bill["is_solar"]
        else:
            # Predict values for missing months
            kwh_val = int(max(1000, slope_kwh * cal_month_idx + intercept_kwh))
            bill_val = int(max(5000, slope_bill * cal_month_idx + intercept_bill))
            is_sol = False
            
        js_sample_bills.append(bill_val)
        js_sample_kwh.append(kwh_val)
        js_sample_solar.append("true" if is_sol else "false")
        
        status_select = f"""<select class="table-input" data-month="{m_idx}" data-type="status" style="padding: 0.25rem;">
                      <option value="grid"{" selected" if not is_sol else ""}>Grid Only</option>
                      <option value="solar"{" selected" if is_sol else ""}>Solar Active</option>
                    </select>"""
                    
        table_rows_html += f"""                  <tr>
                    <td style="padding: 0.5rem 0.25rem; color: var(--text-main); font-weight: 500;">{m_label}</td>
                    <td style="padding: 0.25rem;"><input type="number" class="table-input" data-month="{m_idx}" data-type="bill"></td>
                    <td style="padding: 0.25rem;"><input type="number" class="table-input" data-month="{m_idx}" data-type="kwh"></td>
                    <td style="padding: 0.25rem;">{status_select}</td>
                  </tr>\n"""

    # 1. Replace Table Body
    table_pattern = r'(<tbody id="bill-table-body">)([\s\S]*?)(</tbody>)'
    html_content = re.sub(table_pattern, r'\1\n' + table_rows_html + r'                  \3', html_content)
    
    # 2. Update Table Header (add Status column)
    header_pattern = r'(<thead>[\s\S]*?Consumption \(kWh\)\s*</th>)([\s\S]*?)(</tr>)'
    new_header = r'\1\n                    <th style="padding: 0.5rem 0.25rem; color: var(--text-muted); font-weight: 500;">Status</th>\3'
    html_content = re.sub(header_pattern, new_header, html_content)
    
    # 3. Update JavaScript sample arrays
    bills_pattern = r'const sampleBills\s*=\s*\[[\s\d,]*\];'
    kwh_pattern = r'const sampleKwh\s*=\s*\[[\s\d,]*\];'
    
    html_content = re.sub(bills_pattern, f'const sampleBills = {str(js_sample_bills)};', html_content)
    html_content = re.sub(kwh_pattern, f'const sampleKwh = {str(js_sample_kwh)};', html_content)
    
    # Inject solar sample state array
    solar_state_pattern = r'const sampleSolarState\s*=\s*\[[\s\S]*?\];'
    new_solar_state_code = f'const sampleSolarState = [{", ".join(js_sample_solar)}];'
    
    if re.search(r'const sampleSolarState', html_content):
        html_content = re.sub(solar_state_pattern, new_solar_state_code, html_content)
    else:
        # Inject right below sampleKwh definition
        html_content = html_content.replace(
            f'const sampleKwh = {str(js_sample_kwh)};',
            f'const sampleKwh = {str(js_sample_kwh)};\n      const sampleSolarState = [{", ".join(js_sample_solar)}];'
        )

    # Save changes
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Successfully updated index.html with parsed bill values and layout structure!")
else:
    print("index.html not found.")
