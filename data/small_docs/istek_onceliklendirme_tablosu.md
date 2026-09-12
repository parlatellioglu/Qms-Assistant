---
id: DOC-016
title: İstek Önceliklendirme Tablosu
department: Mühendislik
document_type: procedure
status: published
version: 1.0
author: Kişi 15
created_date: 2025-04-01
last_reviewed: 2025-04-01
language: TR
tags:
  - istek
  - öncelik
  - priority
  - talep
  - mühendislik
  - tablo
---

# İstek Önceliklendirme Tablosu

## 1. Amaç

Gelen taleplerin önceliklendirilmesi için standart bir matris tanımlamak.

## 2. Öncelik Seviyeleri

| Seviye | Kod | Tanım | Yanıt Süresi | Çözüm Süresi |
|--------|-----|-------|-------------|-------------|
| Kritik | P1 | Sistem kesintisi, veri kaybı, güvenlik açığı | 30 dakika | 4 saat |
| Yüksek | P2 | Ana işlevi etkileyen hata, müşteri şikayeti | 2 saat | 24 saat |
| Orta | P3 | Kısmi işlev kaybı, kullanıcı talebi | 8 saat | 3 iş günü |
| Düşük | P4 | İyileştirme önerisi, dökümantasyon güncellemesi | 24 saat | 10 iş günü |

## 3. Etki ve Aciliyet Matrisi

| Aciliyet \ Etki | Düşük Etki | Orta Etki | Yüksek Etki |
|----------------|-----------|----------|------------|
| Düşük | P4 | P3 | P2 |
| Orta | P3 | P3 | P2 |
| Yüksek | P2 | P1 | P1 |

## 4. Önceliklendirme Kriterleri

- **Etki**: Talep karşılanmadığında oluşan iş kaybı
- **Aciliyet**: Talebin ne kadar süre içinde çözülmesi gerektiği
- **Kapsam**: Etkilenen kullanıcı / sistem sayısı
- **İş değeri**: Talebin iş hedeflerine katkısı

## 5. Talep Türüne Göre Varsayılan Öncelik

| Talep Türü | Varsayılan Öncelik |
|-----------|-------------------|
| Üretim hatası - Kritik | P1 |
| Üretim hatası - Major | P2 |
| Üretim hatası - Minor | P3 |
| Yeni özellik talebi | P3 |
| İyileştirme talebi | P4 |
| Bilgi talebi | P4 |
