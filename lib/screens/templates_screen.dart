import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:file_picker/file_picker.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../brand.dart';
import 'login_screen.dart';

class TemplatesScreen extends StatefulWidget { const TemplatesScreen({super.key}); @override State<TemplatesScreen> createState() => _TemplatesScreenState(); }
class _TemplatesScreenState extends State<TemplatesScreen> {
  List<Map<String,dynamic>> items=[]; bool loading=true;
  Future<String> get token async => (await SharedPreferences.getInstance()).getString('jwt_token') ?? '';
  @override void initState(){super.initState(); load();}
  Future<void> load() async { final r=await http.get(Uri.parse('$kApiBaseUrl/v1/templates'),headers:{'Authorization':'Bearer ${await token}'}); if(r.statusCode==200&&mounted)setState(()=>items=List<Map<String,dynamic>>.from(jsonDecode(r.body))); if(mounted)setState(()=>loading=false); }
  Future<void> upload() async { final p=await FilePicker.platform.pickFiles(type:FileType.custom,allowedExtensions:['docx','html','htm','md','txt','pdf']); if(p==null)return; final f=p.files.single; final q=http.MultipartRequest('POST',Uri.parse('$kApiBaseUrl/v1/templates/upload')); q.headers['Authorization']='Bearer ${await token}'; q.files.add(http.MultipartFile.fromBytes('file',f.bytes!,filename:f.name)); await q.send(); await load(); }
  @override Widget build(BuildContext c)=>Scaffold(backgroundColor:BonsoBrand.ink,appBar:AppBar(backgroundColor:BonsoBrand.surface,title:const Text('Plantillas',style:TextStyle(color:Colors.white))),floatingActionButton:FloatingActionButton.extended(onPressed:upload,backgroundColor:BonsoBrand.aqua,label:const Text('Subir plantilla',style:TextStyle(color:Colors.black)),icon:const Icon(Icons.upload_file,color:Colors.black)),body:loading?const Center(child:CircularProgressIndicator()):ListView(padding:const EdgeInsets.all(16),children:items.map((x)=>Card(color:BonsoBrand.surface,child:ListTile(leading:const Icon(Icons.description,color:BonsoBrand.aqua),title:Text(x['nombre'],style:const TextStyle(color:Colors.white)),subtitle:Text('${x['extension']} · ${(x['campos'] as List).length} campos',style:const TextStyle(color:Colors.white54)),trailing:const Icon(Icons.more_vert,color:Colors.white54)))).toList()));
}
