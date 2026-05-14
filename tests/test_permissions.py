import unittest
from unittest.mock import patch

from app import app


class PermissionRoutesTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def _set_session(self, **values):
        with self.client.session_transaction() as session_data:
            session_data.clear()
            session_data.update(values)

    def test_admin_report_requires_download_permission(self):
        self._set_session(logeado=True, usuario='demo', rol='user')

        with patch('rutas.mapa.db.obtener_permisos_usuario', return_value=('user', 0, 0, 0, 0, 0, 0, 0)):
            response = self.client.get('/admin/reporte/dia')

        self.assertEqual(response.status_code, 403)

    def test_csv_report_requires_download_permission(self):
        self._set_session(logeado=True, usuario='demo', rol='user')

        with patch('rutas.mapa.db.obtener_permisos_usuario', return_value=('user', 0, 0, 0, 0, 0, 0, 0)):
            response = self.client.post('/api/reporte_mapa/1', json={'features': []})

        self.assertEqual(response.status_code, 403)

    def test_csv_report_allows_download_permission(self):
        self._set_session(logeado=True, usuario='demo', rol='user')

        with patch('rutas.mapa.db.obtener_permisos_usuario', return_value=('user', 0, 0, 0, 0, 0, 1, 0)):
            response = self.client.post('/api/reporte_mapa/1', json={'features': []})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/csv')


if __name__ == '__main__':
    unittest.main()
