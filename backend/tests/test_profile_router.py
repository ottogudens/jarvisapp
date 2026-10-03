import unittest

from backend.profile_router import select_profiles


class ProfileRouterTests(unittest.TestCase):
    def setUp(self):
        self.profiles = [
            {"nombre": "Mecánico", "instrucciones": "diagnóstico de motor frenos y vehículos"},
            {"nombre": "Redes MikroTik", "instrucciones": "router wifi vlan dhcp firewall conectividad"},
            {"nombre": "Contabilidad", "instrucciones": "facturas impuestos balances pagos"},
            {"nombre": "Experto Frontend UX y Visualización", "instrucciones": "interfaz Flutter accesibilidad diseño gráficos experiencia usuario"},
        ]

    def test_routes_to_relevant_profile(self):
        selected = select_profiles(self.profiles, "El router wifi tiene problemas con DHCP")
        self.assertEqual(selected[0]["nombre"], "Redes MikroTik")

    def test_uses_first_profile_as_safe_fallback(self):
        selected = select_profiles(self.profiles, "Hola")
        self.assertEqual(selected[0]["nombre"], "Mecánico")

    def test_routes_to_frontend_expert(self):
        selected = select_profiles(self.profiles, "Mejora la accesibilidad de la interfaz Flutter")
        self.assertEqual(selected[0]["nombre"], "Experto Frontend UX y Visualización")
