import os, shutil, tempfile, unittest
from pathlib import Path

class CoreFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.mkdtemp(prefix="serv-festa-test-")
        os.environ["SERV_FESTA_DATA_DIR"]=cls.tmp
        os.environ["SERV_FESTA_SECRET_KEY"]="test-secret"
        import config, app.db as dbmod
        config.DATA_DIR=Path(cls.tmp); config.BACKUP_DIR=Path(cls.tmp)/"backups"; config.DB_PATH=Path(cls.tmp)/"serv_festa.db"
        dbmod.DATA_DIR=config.DATA_DIR; dbmod.DB_PATH=config.DB_PATH
        cls.app=__import__("app",fromlist=["create_app"]).create_app(); cls.app.config.update(TESTING=True)
        cls.client=cls.app.test_client()

    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.tmp,ignore_errors=True)

    def csrf(self):
        with self.client.session_transaction() as s: return s.get("csrf_token")

    def test_1_setup_login_purchase_sale_cancel_flow(self):
        r=self.client.get("/setup"); self.assertEqual(r.status_code,200)
        token=self.csrf(); self.assertIsNotNone(token)
        r=self.client.post("/setup",data={"csrf_token":token,"name":"Administrador","username":"admin","password":"senha-local-forte"},follow_redirects=True); self.assertIn(b"Usu\xc3\xa1rio",r.data)
        token=self.csrf(); self.client.post("/login",data={"csrf_token":token,"username":"admin","password":"senha-local-forte"})
        token=self.csrf();
        data={"csrf_token":token,"product_id":["1"],"quantity":["100"],"unit_cost":["4,00"],"supplier":"Teste"}
        r=self.client.post("/purchases",data=data); self.assertEqual(r.status_code,302)
        with self.client.session_transaction() as s: token=s["csrf_token"]
        r=self.client.post("/api/sales",json={"items":[{"product_id":1,"quantity":20}]},headers={"X-CSRF-Token":token}); self.assertEqual(r.status_code,200)
        import config
        from app.db import get_db
        with get_db() as db:
            p=db.execute("SELECT stock_qty,avg_cost_cents FROM products WHERE id=1").fetchone(); self.assertEqual(p["stock_qty"],80); self.assertEqual(p["avg_cost_cents"],400)
            sale=db.execute("SELECT id,revenue_cents,cogs_cents,gross_profit_cents FROM sales").fetchone(); self.assertEqual((sale["revenue_cents"],sale["cogs_cents"],sale["gross_profit_cents"]),(16000,8000,8000)); sale_id=sale["id"]
        token=self.csrf(); r=self.client.post(f"/sales/{sale_id}/cancel",data={"csrf_token":token,"reason":"Lançamento incorreto"}); self.assertEqual(r.status_code,302)
        with get_db() as db:
            self.assertEqual(db.execute("SELECT stock_qty FROM products WHERE id=1").fetchone()[0],100)
            self.assertEqual(db.execute("SELECT status FROM sales WHERE id=?",(sale_id,)).fetchone()[0],"cancelled")

    def test_2_insufficient_stock_is_atomic(self):
        with self.client.session_transaction() as s: token=s.get("csrf_token")
        if not token:
            self.client.get("/setup"); token=self.csrf(); self.client.post("/setup",data={"csrf_token":token,"name":"Administrador","username":"admin","password":"senha-local-forte"}); token=self.csrf(); self.client.post("/login",data={"csrf_token":token,"username":"admin","password":"senha-local-forte"})
        with self.client.session_transaction() as s: token=s["csrf_token"]
        r=self.client.post("/api/sales",json={"items":[{"product_id":1,"quantity":999}]},headers={"X-CSRF-Token":token}); self.assertEqual(r.status_code,400)
        from app.db import get_db
        with get_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sales").fetchone()[0],1)

    def test_3_pages_render(self):
        token=self.csrf()
        response=self.client.post("/prices",data={"csrf_token":token,"product_id":["1"],"sale_price":["8,00"],"min_stock":["110"],"ideal_stock":["120"]})
        self.assertEqual(response.status_code,302)
        response=self.client.get("/")
        self.assertIn(b"Alertas de estoque",response.data)
        self.assertIn(b"Espeto de Carne",response.data)
        for path in ["/", "/sale", "/sales", "/purchases", "/stock", "/inventory", "/products", "/reports", "/close/daily", "/close/monthly", "/need-to-buy", "/audit", "/users", "/settings"]:
            response=self.client.get(path)
            self.assertEqual(response.status_code,200,path)

if __name__=="__main__": unittest.main()

