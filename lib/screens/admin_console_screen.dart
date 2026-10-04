import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../brand.dart';
import 'admin_screen.dart';
import 'login_screen.dart';

class AdminConsoleScreen extends StatefulWidget { const AdminConsoleScreen({super.key}); @override State<AdminConsoleScreen> createState()=>_AdminConsoleScreenState(); }
class _AdminConsoleScreenState extends State<AdminConsoleScreen> {
  Map<String,dynamic>? _data; bool _loading=true;
  @override void initState(){super.initState();_load();}
  Future<void> _load() async { final token=(await SharedPreferences.getInstance()).getString('jwt_token'); try{final r=await http.get(Uri.parse('$kApiBaseUrl/v1/admin/operations/overview'),headers:{'Authorization':'Bearer $token'});if(r.statusCode==200)_data=jsonDecode(r.body);}finally{if(mounted)setState(()=>_loading=false);}}
  @override Widget build(BuildContext context){final k=_data?['kpis']??{};final subs=(_data?['subscriptions']??[]) as List;return Scaffold(backgroundColor:BonsoBrand.ink,appBar:AppBar(title:const Text('Bonso · Consola de operaciones'),actions:[IconButton(onPressed:_load,icon:const Icon(Icons.refresh))]),body:_loading?const Center(child:CircularProgressIndicator()):RefreshIndicator(onRefresh:_load,child:ListView(padding:const EdgeInsets.all(24),children:[const Text('Operación comercial',style:TextStyle(fontSize:28,fontWeight:FontWeight.bold)),const SizedBox(height:18),Wrap(spacing:12,runSpacing:12,children:[_kpi('Clientes',k['clientes']),_kpi('Suscripciones activas',k['suscripciones_activas']),_kpi('Cobros pendientes',k['cobros_pendientes']),_kpi('Tokens',k['tokens'])]),const SizedBox(height:28),const Text('Facturación reciente',style:TextStyle(fontSize:18,fontWeight:FontWeight.bold)),...subs.map((s)=>Card(color:BonsoBrand.surface,child:ListTile(title:Text(s['organizacion']??'',style:const TextStyle(color:Colors.white)),subtitle:Text('${s['amount']} ${s['currency']} · ${s['status']}',style:const TextStyle(color:Colors.white70)),trailing:const Icon(Icons.receipt_long,color:BonsoBrand.aqua))),),const SizedBox(height:20),ElevatedButton.icon(onPressed:()=>Navigator.push(context,MaterialPageRoute(builder:(_)=>const AdminScreen())),icon:const Icon(Icons.settings),label:const Text('Administrar clientes, planes y perfiles'),style:ElevatedButton.styleFrom(backgroundColor:BonsoBrand.aqua,foregroundColor:Colors.black))])));}
  Widget _kpi(String label,dynamic value)=>Container(width:170,padding:const EdgeInsets.all(16),decoration:BoxDecoration(color:BonsoBrand.surface,borderRadius:BorderRadius.circular(14)),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text('$value',style:const TextStyle(fontSize:24,color:BonsoBrand.aqua,fontWeight:FontWeight.bold)),Text(label,style:const TextStyle(color:Colors.white70))]));
}
