import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import '../brand.dart';
import 'login_screen.dart';

class BillingScreen extends StatefulWidget {
  const BillingScreen({super.key});

  @override
  State<BillingScreen> createState() => _BillingScreenState();
}

class _BillingScreenState extends State<BillingScreen> {
  Map<String, dynamic>? _data;
  List<dynamic> _plans = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final token = (await SharedPreferences.getInstance()).getString('jwt_token');
    try {
      final responses = await Future.wait([
        http.get(Uri.parse('$kApiBaseUrl/v1/billing/status'), headers: {'Authorization': 'Bearer $token'}),
        http.get(Uri.parse('$kApiBaseUrl/v1/billing/plans'), headers: {'Authorization': 'Bearer $token'}),
      ]);
      if (responses[0].statusCode == 200) _data = jsonDecode(responses[0].body);
      if (responses[1].statusCode == 200) _plans = jsonDecode(responses[1].body);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _checkout() async {
    final plan = await showDialog<dynamic>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: const Text('Contratar o cambiar plan', style: TextStyle(color: Colors.white)),
        content: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: _plans.map((plan) => ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('${plan['nombre']}', style: const TextStyle(color: Colors.white)),
                subtitle: Text('${plan['precio_mensual']} ${plan['moneda']} · ${plan['tokens_mensuales']} tokens', style: const TextStyle(color: Colors.white70)),
                onTap: () => Navigator.pop(context, plan),
              )).toList(),
            ),
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancelar'))],
      ),
    );
    if (plan == null) return;
    final token = (await SharedPreferences.getInstance()).getString('jwt_token');
    final response = await http.post(
      Uri.parse('$kApiBaseUrl/v1/billing/checkout/${plan['id_plan']}'),
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode != 200) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No se pudo abrir el cobro: ${response.body}')));
      return;
    }
    final url = jsonDecode(response.body)['checkout_url']?.toString();
    if (url != null) await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    final data = _data;
    final used = (data?['tokens_consumidos'] ?? 0) as int;
    final limit = (data?['tokens_mensuales'] ?? 0) as int;
    return Scaffold(
      backgroundColor: BonsoBrand.ink,
      appBar: AppBar(title: const Text('Plan y facturación')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : SafeArea(
              top: false,
              child: LayoutBuilder(
                builder: (context, constraints) => SingleChildScrollView(
                  padding: EdgeInsets.all(constraints.maxWidth < 420 ? 16 : 24),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 700),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('${data?['plan'] ?? 'Sin plan'}', style: const TextStyle(fontSize: 28, color: Colors.white, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 8),
                        Text('Estado: ${data?['subscription_status'] ?? 'none'}', style: const TextStyle(color: BonsoBrand.aqua)),
                        const SizedBox(height: 28),
                        Text('Uso mensual: $used / $limit tokens', style: const TextStyle(color: Colors.white70)),
                        const SizedBox(height: 10),
                        LinearProgressIndicator(value: limit > 0 ? (used / limit).clamp(0, 1) : 0, color: BonsoBrand.aqua, backgroundColor: BonsoBrand.surfaceRaised),
                        const SizedBox(height: 28),
                        Text('Precio: ${data?['precio_mensual'] ?? 0} ${data?['moneda'] ?? 'CLP'} / mes', style: const TextStyle(color: Colors.white, fontSize: 18)),
                        const SizedBox(height: 36),
                        SizedBox(
                          width: constraints.maxWidth < 420 ? double.infinity : null,
                          child: ElevatedButton.icon(
                            onPressed: _checkout,
                            icon: const Icon(Icons.credit_card),
                            label: const Text('Gestionar suscripción'),
                            style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.lime, foregroundColor: Colors.black, minimumSize: const Size(0, 48)),
                          ),
                        ),
                        const SizedBox(height: 12),
                        const Text('Los cobros son procesados de forma segura por Mercado Pago.', style: TextStyle(color: Colors.white54)),
                      ],
                    ),
                  ),
                ),
              ),
            ),
    );
  }
}
