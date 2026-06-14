"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BookOpen, CalendarIcon, FileText } from "lucide-react";
import { FaqTab } from "./components/faq-tab";
import { EventTab } from "./components/event-tab";
import { DocumentTab } from "./components/document-tab";
import { PageContainer } from "@/components/page-container";

export default function KnowledgeBasePage() {
  return (
    <PageContainer>
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Base de Conhecimento</h1>
        <p className="text-muted-foreground mt-1">
          Gerencie informações locais e eventos para a prototipagem do Agente
        </p>
      </div>

      <Tabs defaultValue="faqs" className="w-full space-y-6">
        <TabsList className="bg-muted/50 p-1">
          <TabsTrigger value="faqs" className="gap-2 px-4 py-2 text-sm font-medium transition-all">
            <BookOpen className="h-4 w-4" /> FAQs
          </TabsTrigger>
          <TabsTrigger value="events" className="gap-2 px-4 py-2 text-sm font-medium transition-all">
            <CalendarIcon className="h-4 w-4" /> Eventos
          </TabsTrigger>
          <TabsTrigger value="documents" className="gap-2 px-4 py-2 text-sm font-medium transition-all">
            <FileText className="h-4 w-4" /> Documentos
          </TabsTrigger>
        </TabsList>

        <TabsContent value="faqs" className="mt-0 outline-none">
          <FaqTab />
        </TabsContent>

        <TabsContent value="events" className="mt-0 outline-none">
          <EventTab />
        </TabsContent>

        <TabsContent value="documents" className="mt-0 outline-none">
          <DocumentTab />
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
