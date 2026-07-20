"""IntelliFile Manager — Kivy Mobile App (Android APK)

A mobile-first interface for IntelliFile Manager with Arabic RTL support.
This app wraps the core engines and provides a touch-friendly UI.

Build APK:
    buildozer android debug

Run on desktop:
    python mobile/main.py
"""

from __future__ import annotations

import os
import sys

# Ensure project root is in path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.recycleview import RecycleView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.metrics import dp
from kivy.core.window import Window

# Arabic RTL helper
RTL_MARK = '\u200F'


KV = '''
#:import dp kivy.metrics.dp

<MainScreen>:
   BoxLayout:
		orientation: 'vertical'
		
		MDToolbar:
			title: 'IntelliFile Manager'
			elevation: 10
			
		BoxLayout:
			orientation: 'vertical'
			padding: dp(16)
			spacing: dp(8)
			
			TextInput:
				id: search_input
				hint_text: 'بحث في الملفات...'
				size_hint_y: None
				height: dp(48)
				on_text_validate: root.do_search(self.text)
				
			Button:
				text: 'بحث'
				size_hint_y: None
				height: dp(48)
				on_press: root.do_search(search_input.text)
				
			ScrollView:
				Label:
					id: result_label
					text: 'مرحباً بك في IntelliFile Manager\\nاضغط بحث للبدء'
					halign: 'right'
					valign: 'top'
					text_size: self.width, None
					size_hint_y: None
					height: self.texture_size[1]
					
			BoxLayout:
				size_hint_y: None
				height: dp(48)
				spacing: dp(8)
				
				Button:
					text: 'تصنيف'
					on_press: root.do_classify()
					
				Button:
					text: 'وسوم'
					on_press: root.do_tags()
					
				Button:
					text: 'NER طبي'
					on_press: root.do_ner()
					
				Button:
					text: 'صحة'
					on_press: root.do_health()
'''


class MainScreen(Screen):
    """الشاشة الرئيسية للتطبيق"""
    
    def do_search(self, query):
        if not query.strip():
            return
        try:
            from src.core.hybrid_search import HybridSearchEngine
            engine = HybridSearchEngine()
            results = engine.search(query, top_k=10)
            if results:
                text = '\n'.join(
                    f'📄 {r["id"][:50]}... (score: {r["rrf_score"]})'
                    for r in results
                )
            else:
                text = 'لا توجد نتائج'
        except Exception as e:
            text = f'خطأ: {e}'
        self.ids.result_label.text = RTL_MARK + text
    
    def do_classify(self):
        try:
            from src.core.classifier import SmartFileClassifier
            clf = SmartFileClassifier()
            import tempfile
            results = clf.batch_classify(tempfile.gettempdir())
            stats = clf.get_stats(results)
            text = '\n'.join(f'{k}: {v}' for k, v in stats.items())
        except Exception as e:
            text = f'خطأ: {e}'
        self.ids.result_label.text = RTL_MARK + text
    
    def do_tags(self):
        try:
            from src.core.smart_tagger import SmartTagger
            tagger = SmartTagger()
            import tempfile
            tags = tagger.get_all_tags(tempfile.gettempdir())
            text = '\n'.join(f'{k}: {v}' for k, v in sorted(tags.items(), key=lambda x: -x[1])[:20])
        except Exception as e:
            text = f'خطأ: {e}'
        self.ids.result_label.text = RTL_MARK + text
    
    def do_ner(self):
        sample = 'المريض أحمد يعاني من مرض السكري ويأخذ الميتفورمين 500 ملغ'
        try:
            from src.core.medical_ner import ArabicMedicalNER
            ner = ArabicMedicalNER()
            result = ner.extract(sample)
            lines = [f'أمراض: {result.diagnosis}', f'أدوية: {result.medications}']
            text = '\n'.join(lines)
        except Exception as e:
            text = f'خطأ: {e}'
        self.ids.result_label.text = RTL_MARK + text
    
    def do_health(self):
        try:
            import httpx
            r = httpx.get('http://localhost:8421/api/health', timeout=3)
            data = r.json()
            text = f'الحالة: {data["status"]}\nالإصدار: {data["version"]}\n'
            text += '\n'.join(f'{k}: {"✅" if v else "❌"}' for k, v in data['engines'].items())
        except Exception:
            text = 'الخادم غير متاح — وضع عدم الاتصال'
        self.ids.result_label.text = RTL_MARK + text


class IntelliFileApp(App):
    """تطبيق IntelliFile Manager"""
    
    def build(self):
        self.title = 'IntelliFile Manager'
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        return sm
    
    def on_pause(self):
        return True
    
    def on_resume(self):
        pass


if __name__ == '__main__':
    IntelliFileApp().run()
