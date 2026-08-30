"""
End-to-end flow test v2:
  Full pipeline + explicit notification verification + dataset export.
"""
import asyncio, httpx, json, time, base64

BASE = "http://localhost:8000"
TS = str(int(time.time()))


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as c:

        # ── 1. Admin login ──
        r = await c.post("/api/auth/login", data={
            "username": "admin@arqulat.com", "password": "adminpassword"
        })
        assert r.status_code == 200, f"Admin login failed: {r.text}"
        admin_token = r.json()["access_token"]
        ah = {"Authorization": f"Bearer {admin_token}"}
        print("[OK] Admin login")

        # ── 2. Taxonomy ──
        r = await c.post("/api/taxonomy/phases", json={"name": f"Phase-{TS}"}, headers=ah)
        assert r.status_code == 201, f"Phase: {r.text}"
        phase_id = r.json()["id"]

        r = await c.post(f"/api/taxonomy/phases/{phase_id}/subphases",
                         json={"name": f"Sub-{TS}"}, headers=ah)
        assert r.status_code == 201, f"Subphase: {r.text}"
        sub_id = r.json()["id"]

        r = await c.post(f"/api/taxonomy/subphases/{sub_id}/categories",
                         json={"name": f"Cat-{TS}"}, headers=ah)
        assert r.status_code == 201, f"Category: {r.text}"
        cat_id = r.json()["id"]
        print("[OK] Taxonomy")

        # ── 3. Prompt ──
        r = await c.post("/api/prompts", json={
            "category_id": cat_id,
            "prompt_text": f"Generate brick wall {TS}",
            "tags": ["brick"], "force_create": True
        }, headers=ah)
        assert r.status_code == 201, f"Prompt: {r.text}"
        prompt_id = r.json()["id"]
        print("[OK] Prompt")

        # ── 4. Batch ──
        r = await c.post("/api/batches", json={"name": f"Batch-{TS}"}, headers=ah)
        assert r.status_code == 201
        batch_id = r.json()["id"]

        r = await c.post(f"/api/batches/{batch_id}/prompts",
                         json={"prompt_id": prompt_id}, headers=ah)
        assert r.status_code == 201
        print("[OK] Batch + prompt added")

        # ── 5. Users: contributor, reviewer, lead ──
        r = await c.post("/api/users", json={
            "email": f"c-{TS}@t.com", "password": "p123", "display_name": f"C-{TS}"
        }, headers=ah)
        assert r.status_code == 201
        contrib_id = r.json()["id"]

        r = await c.post("/api/users", json={
            "email": f"r-{TS}@t.com", "password": "p123", "display_name": f"R-{TS}"
        }, headers=ah)
        assert r.status_code == 201
        reviewer_id = r.json()["id"]

        r = await c.post("/api/users", json={
            "email": f"l-{TS}@t.com", "password": "p123", "display_name": f"L-{TS}"
        }, headers=ah)
        assert r.status_code == 201
        lead_id = r.json()["id"]

        # Promote
        r = await c.patch(f"/api/users/{reviewer_id}/role", json={"role": "reviewer"}, headers=ah)
        assert r.status_code == 200
        r = await c.patch(f"/api/users/{lead_id}/role", json={"role": "lead"}, headers=ah)
        assert r.status_code == 200
        print("[OK] Users created (contributor, reviewer, lead)")

        # ── 6. Assign ──
        r = await c.post(f"/api/batches/{batch_id}/assignments", json={
            "prompt_ids": [prompt_id],
            "contributor_id": contrib_id,
            "reviewer_id": reviewer_id,
        }, headers=ah)
        assert r.status_code == 200
        print(f"[OK] Assignment: {r.json()}")

        # ── 7. Contributor edits + submits ──
        r = await c.post("/api/auth/login", data={"username": f"c-{TS}@t.com", "password": "p123"})
        assert r.status_code == 200
        ch = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = await c.get("/api/entries", params={"batch_id": batch_id}, headers=ch)
        assert r.status_code == 200
        entry_id = r.json()[0]["id"]

        r = await c.patch(f"/api/entries/{entry_id}",
                          json={"script": "import bpy; bpy.ops.mesh.primitive_cube_add()"}, headers=ch)
        assert r.status_code == 200

        r = await c.post(f"/api/entries/{entry_id}/submit", headers=ch)
        assert r.status_code == 200
        print("[OK] Contributor submitted entry")

        # ── 8. Worker claims + completes ──
        wh = {"X-Worker-Token": "worker_secret_token"}
        r = await c.post("/api/workers/register", json={"name": f"w-{TS}"}, headers=wh)
        assert r.status_code == 201
        worker_id = r.json()["id"]

        r = await c.post("/api/jobs/claim", params={"worker_id": worker_id}, headers=wh)
        assert r.status_code == 200
        job = r.json()
        assert job is not None
        job_id = job["id"]

        r = await c.post(f"/api/jobs/{job_id}/complete", json={
            "render_file_b64": base64.b64encode(b"img").decode(),
            "glb_file_b64": base64.b64encode(b"glb").decode(),
        }, headers=wh)
        assert r.status_code == 200 and r.json()["status"] == "done"
        print("[OK] Worker claimed + completed job")

        # ── 9. TEST: Reviewer does needs_fix -> notification to contributor ──
        r = await c.post("/api/auth/login", data={"username": f"r-{TS}@t.com", "password": "p123"})
        assert r.status_code == 200
        rh = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = await c.post(f"/api/reviews/{entry_id}",
                         json={"action": "needs_fix", "notes": "Fix the scale"}, headers=rh)
        assert r.status_code == 201, f"Review (needs_fix) failed: {r.text}"
        print("[OK] Reviewer marked needs_fix")

        # Verify notification was created for contributor
        r = await c.get("/api/notifications", headers=ch)
        assert r.status_code == 200, f"Get notifications failed: {r.text}"
        contrib_notifs = r.json()
        needs_fix_notifs = [n for n in contrib_notifs if n["action"] == "needs_fix"]
        assert len(needs_fix_notifs) >= 1, f"Expected needs_fix notification for contributor, got: {contrib_notifs}"
        print(f"[OK] VERIFIED: Contributor received needs_fix notification (id={needs_fix_notifs[0]['id']})")

        # ── 10. Contributor fixes and resubmits ──
        r = await c.patch(f"/api/entries/{entry_id}",
                          json={"script": "import bpy; bpy.ops.mesh.primitive_cube_add(size=2)"}, headers=ch)
        assert r.status_code == 200

        r = await c.post(f"/api/entries/{entry_id}/submit", headers=ch)
        assert r.status_code == 200
        print("[OK] Contributor resubmitted")

        # Worker picks up and completes the new job
        r = await c.post("/api/jobs/claim", params={"worker_id": worker_id}, headers=wh)
        assert r.status_code == 200
        job2 = r.json()
        assert job2 is not None
        r = await c.post(f"/api/jobs/{job2['id']}/complete", json={
            "render_file_b64": base64.b64encode(b"img2").decode(),
            "glb_file_b64": base64.b64encode(b"glb2").decode(),
        }, headers=wh)
        assert r.status_code == 200
        print("[OK] Worker completed re-render job")

        # ── 11. TEST: Lead override -> notification to original reviewer ──
        r = await c.post("/api/auth/login", data={"username": f"l-{TS}@t.com", "password": "p123"})
        assert r.status_code == 200
        lh = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = await c.post(f"/api/reviews/{entry_id}",
                         json={"action": "approved", "notes": "Lead approves"}, headers=lh)
        assert r.status_code == 201, f"Lead override review failed: {r.text}"
        review_data = r.json()
        assert review_data["is_lead_override"] == True, "Expected is_lead_override=True"
        print("[OK] Lead override approved")

        # Verify notification was created for original reviewer
        r = await c.get("/api/notifications", headers=rh)
        assert r.status_code == 200, f"Get reviewer notifications failed: {r.text}"
        reviewer_notifs = r.json()
        override_notifs = [n for n in reviewer_notifs if n["action"] == "lead_override"]
        assert len(override_notifs) >= 1, f"Expected lead_override notification for reviewer, got: {reviewer_notifs}"
        print(f"[OK] VERIFIED: Reviewer received lead_override notification (id={override_notifs[0]['id']})")

        # ── 12. Check entry is approved ──
        r = await c.get("/api/entries", params={"batch_id": batch_id}, headers=ch)
        entry = r.json()[0]
        assert entry["status"] == "approved", f"Expected approved, got {entry['status']}"
        print("[OK] Entry status: approved")

        # ── 13. TEST: Export dataset ──
        r = await c.get("/api/export/dataset", headers=ah)
        assert r.status_code == 200, f"Export failed: {r.text}"
        lines = r.text.strip().split("\n")
        assert len(lines) >= 1, "Export returned no data"
        row = json.loads(lines[-1])
        assert "prompt" in row and "script" in row and "category" in row
        print(f"[OK] VERIFIED: Dataset export ({len(lines)} lines). Sample: {json.dumps(row)[:120]}...")

        # ── 14. Worker health ──
        r = await c.get("/api/workers/health", headers=wh)
        assert r.status_code == 200
        print(f"[OK] Worker health: {json.dumps(r.json(), indent=2)}")

        print("\n=== ALL E2E CHECKS PASSED (pipeline + notifications + export) ===")


if __name__ == "__main__":
    asyncio.run(main())
