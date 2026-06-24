from pydantic import BaseModel

class StockRequest(BaseModel):
    ticker: str
    start_date: str
    end_date: str

class StockResponse(BaseModel):
    ticker: str
    historical_data: dict