from ninja import Router

router = Router(tags=["products"])

@router.get("/")
def health(request):
  return {"message": "success"}