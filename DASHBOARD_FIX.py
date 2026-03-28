@app.get("/")
async def dashboard():
    """Serve dashboard HTML"""
    try:
        return FileResponse("/app/webui/dashboard.html")
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        return {"error": f"Dashboard not found: {e}"}
