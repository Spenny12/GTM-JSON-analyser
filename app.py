import streamlit as st
import json
import google.generativeai as genai
import pandas as pd
from io import StringIO

st.set_page_config(page_title="GTM JSON Analyser")

def analyze_gtm_data(api_key, gtm_json):
    """
    Extracts relevant parts from GTM JSON and sends to Gemini for analysis.
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name='gemini-3-flash-preview',
        generation_config={"temperature": 0}
    )
    
    # Check for nested structure in "data" key (common in some GTM debugger exports)
    containers = gtm_json.get("containers", [])
    if not containers and "data" in gtm_json:
        containers = gtm_json.get("data", {}).get("containers", [])
    
    # Pruning the JSON to stay within sensible token limits while keeping crucial info
    pruned_data = {
        "domain": gtm_json.get("name"),
        "containers": [
            {
                "publicId": c.get("publicId"),
                "product": c.get("product"),
                "version": c.get("version")
            } for c in containers
        ],
        "message_summaries": []
    }
    
    # Extract messages: Check top-level, then data-level, then within containers
    messages = gtm_json.get("messages", [])
    if not messages and "data" in gtm_json:
        messages = gtm_json.get("data", {}).get("messages", [])
    
    if not messages:
        # Fallback: collect messages from all containers
        for c in containers:
            messages.extend(c.get("messages", []))
    
    # Extract only essential info from messages (events, tags fired, consent)
    for msg in messages[:100]: # Limit to first 100 messages for breadth vs depth
        summary = {
            "eventName": msg.get("eventName"),
            "index": msg.get("index"),
            "consentData": msg.get("consentData"),
            "tags": [
                {
                    "name": t.get("name"),
                    "status": t.get("status"),
                    "firingStatus": t.get("firingStatus")
                } for t in msg.get("tagInfo", [])
            ]
        }
        pruned_data["message_summaries"].append(summary)

    prompt = f"""
    You are a Technical SEO and Web Analytics expert. 
    Analyse the following GTM/GA4 Debugger JSON summary for tracking issues and optimisation opportunities.
    Focus on:
    1. Cookie Consent: Check if tags are firing before consent is granted (ad_storage, analytics_storage).
    2. Double Tracking: Identify if multiple tags are firing for the same event.
    3. Broken/Redundant Tags: Look for tags that appear to fail or use outdated methods.
    4. Optimisation: Suggest improvements for container performance or data layer structure.
    5. Consent Mode: Check if Consent Mode (v2) is correctly implemented based on the message data.

    GTM Data Summary:
    {json.dumps(pruned_data, indent=2)}
    
    Return the analysis in a JSON object with the following structure:
    {{
        "report_markdown": "A detailed, concise markdown report with sections for Critical Issues, Potential Risks, and Optimisation Opportunities.",
        "issues_table": [
            {{
                "Issue": "string",
                "Priority": "Critical|High|Medium|Low|Advisory",
                "Recommended Action": "string",
                "Documentation Link": "URL to Google documentation or 'Validate'"
            }}
        ]
    }}
    
    Rules:
    - Use British English spelling (e.g., 'optimisation' not 'optimization', 'categorise' not 'categorize').
    - Documentation Link: ONLY use verified Google documentation URLs (e.g., from support.google.com/tagmanager/ or developers.google.com/tag-platform/). 
    - CRITICAL: DO NOT hallucinate URLs. If you are not 100% certain of a specific deep link, use 'Validate' or a reliable top-level category link.
    - Return ONLY the JSON object.
    """
    
    try:
        response = model.generate_content(prompt)
        # Clean up Markdown formatting if Gemini includes it
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())
    except Exception as e:
        return f"Error during analysis: {str(e)}"

def main():
    st.title("GTM Debugger JSON Analyser")
    st.markdown("""
    This tool analyses GTM Debugger export files to identify tracking issues,
    consent mode misconfigurations, and optimisation opportunities.
    """)

    with st.sidebar:
        st.header("Configuration")
        api_key = st.text_input("Gemini API Key", type="password", help="Get your key from https://aistudio.google.com/")
        st.info("Your API key is not stored and is only used for the current session.")

    uploaded_file = st.file_uploader("Upload GTM Debugger JSON", type=["json"])

    if uploaded_file is not None:
        try:
            # Load and show a preview
            gtm_data = json.load(uploaded_file)
            
            st.success("File uploaded successfully!")
            
            with st.expander("View Raw Data Summary"):
                containers = gtm_data.get("containers", [])
                if not containers and "data" in gtm_data:
                    containers = gtm_data.get("data", {}).get("containers", [])
                
                messages = gtm_data.get("messages", [])
                if not messages and "data" in gtm_data:
                    messages = gtm_data.get("data", {}).get("messages", [])
                
                if not messages:
                    for c in containers:
                        messages.extend(c.get("messages", []))

                st.json({
                    "Domain": gtm_data.get("name"),
                    "Containers": [c.get("publicId") for c in containers],
                    "Events Count": len(messages)
                })

            if st.button("Analyse with Gemini"):
                if not api_key:
                    st.error("Please provide a Gemini API Key in the sidebar.")
                else:
                    with st.spinner("Analysing tracking data..."):
                        analysis_result = analyze_gtm_data(api_key, gtm_data)
                        
                        if isinstance(analysis_result, dict) and "report_markdown" in analysis_result:
                            st.markdown("### Analysis Report")
                            st.markdown(analysis_result["report_markdown"])
                            
                            st.markdown("### Prioritisation Matrix")
                            df = pd.DataFrame(analysis_result["issues_table"])
                            
                            # Custom styling for priority
                            def color_priority(val):
                                colors = {
                                    "Critical": "background-color: #ff4b4b; color: white;",
                                    "High": "background-color: #ff7c43; color: white;",
                                    "Medium": "background-color: #f6c85f; color: black;",
                                    "Low": "background-color: #a8dadc; color: black;",
                                    "Advisory": "background-color: #e9ecef; color: black;"
                                }
                                return colors.get(val, "")

                            # Use st.column_config to make the link clickable
                            st.dataframe(
                                df.style.applymap(color_priority, subset=["Priority"]),
                                column_config={
                                    "Documentation Link": st.column_config.LinkColumn(
                                        "Documentation Link",
                                        help="Click to open Google documentation",
                                        validate="^https?://.*",
                                        display_text="View Documentation"
                                    )
                                },
                                use_container_width=True,
                                hide_index=True
                            )
                            
                            # Export option
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="Download Summary CSV",
                                data=csv,
                                file_name="gtm_analysis_summary.csv",
                                mime="text/csv",
                            )
                        else:
                            st.error(str(analysis_result))
        
        except Exception as e:
            st.error(f"Failed to parse JSON: {e}")

if __name__ == "__main__":
    main()
