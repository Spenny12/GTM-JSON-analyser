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
    model = genai.GenerativeModel('gemini-3-flash-preview')
    
    # Pruning the JSON to stay within sensible token limits while keeping crucial info
    pruned_data = {
        "domain": gtm_json.get("name"),
        "containers": [
            {
                "publicId": c.get("publicId"),
                "product": c.get("product"),
                "version": c.get("version")
            } for c in gtm_json.get("containers", [])
        ],
        "message_summaries": []
    }
    
    # Extract only essential info from messages (events, tags fired, consent)
    messages = gtm_json.get("messages", [])
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
    Analyse the following GTM/GA4 Debugger JSON summary for tracking issues and optimization opportunities.
    Focus on:
    1. Cookie Consent: Check if tags are firing before consent is granted (ad_storage, analytics_storage).
    2. Double Tracking: Identify if multiple tags are firing for the same event.
    3. Broken/Redundant Tags: Look for tags that appear to fail or use outdated methods.
    4. Optimization: Suggest improvements for container performance or data layer structure.
    5. Consent Mode: Check if Consent Mode (v2) is correctly implemented based on the message data.

    GTM Data Summary:
    {json.dumps(pruned_data, indent=2)}
    
    Provide a concise report with:
    - Critical Issues (Immediate fixes)
    - Potential Risks
    - Optimization Opportunities
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error during analysis: {str(e)}"

def main():
    st.title("GTM Debugger JSON Analyser")
    st.markdown("""
    This tool analyses GTM Debugger export files to identify tracking issues,
    consent mode misconfigurations, and optimization opportunities.
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
                st.json({
                    "Domain": gtm_data.get("name"),
                    "Containers": [c.get("publicId") for c in gtm_data.get("containers", [])],
                    "Events Count": len(gtm_data.get("messages", [])) if "messages" in gtm_data else 0
                })

            if st.button("Analyse with Gemini"):
                if not api_key:
                    st.error("Please provide a Gemini API Key in the sidebar.")
                else:
                    with st.spinner("Analyzing tracking data..."):
                        analysis = analyze_gtm_data(api_key, gtm_data)
                        st.markdown("### Analysis Report")
                        st.markdown(analysis)
        
        except Exception as e:
            st.error(f"Failed to parse JSON: {e}")

if __name__ == "__main__":
    main()
