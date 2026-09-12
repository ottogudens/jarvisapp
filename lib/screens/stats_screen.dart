/// J.A.R.V.I.S. — Dashboard Analítico y Comercial

import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';

class JarvisStatsScreen extends StatelessWidget {
  const JarvisStatsScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        title: const Text('Dashboard Comercial J.A.R.V.I.S.'),
        backgroundColor: const Color(0xFF1E293B),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // --- KPI: Facturación mensual ---
            Card(
              color: const Color(0xFF1E293B),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              child: const ListTile(
                contentPadding: EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                leading: Icon(Icons.attach_money, color: Colors.greenAccent, size: 36),
                title: Text(
                  '\$4,520,000',
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                    color: Colors.greenAccent,
                  ),
                ),
                subtitle: Text(
                  'Facturación Mensual',
                  style: TextStyle(color: Colors.white70, fontSize: 14),
                ),
              ),
            ),

            const SizedBox(height: 24),

            // --- KPI: Órdenes activas ---
            Card(
              color: const Color(0xFF1E293B),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              child: const ListTile(
                contentPadding: EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                leading: Icon(Icons.build_circle, color: Colors.cyanAccent, size: 36),
                title: Text(
                  '47',
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                    color: Colors.cyanAccent,
                  ),
                ),
                subtitle: Text(
                  'Órdenes de Trabajo Activas',
                  style: TextStyle(color: Colors.white70, fontSize: 14),
                ),
              ),
            ),

            const SizedBox(height: 32),

            // --- Gráfico: Distribución por marca ---
            const Text(
              'Distribución por Marca',
              style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            SizedBox(
              height: 220,
              child: PieChart(
                PieChartData(
                  sectionsSpace: 3,
                  centerSpaceRadius: 45,
                  sections: [
                    PieChartSectionData(
                      color: Colors.cyan,
                      value: 40,
                      title: 'Ford\n40%',
                      radius: 55,
                      titleStyle: const TextStyle(fontSize: 11, color: Colors.white, fontWeight: FontWeight.bold),
                    ),
                    PieChartSectionData(
                      color: Colors.blue,
                      value: 35,
                      title: 'Toyota\n35%',
                      radius: 55,
                      titleStyle: const TextStyle(fontSize: 11, color: Colors.white, fontWeight: FontWeight.bold),
                    ),
                    PieChartSectionData(
                      color: Colors.blueGrey,
                      value: 25,
                      title: 'Otros\n25%',
                      radius: 55,
                      titleStyle: const TextStyle(fontSize: 11, color: Colors.white, fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
